const CACHE_VERSION = 'v1.0.0';
const CACHE_NAME = `dialtone-${CACHE_VERSION}`;
const API_CACHE = `dialtone-api-${CACHE_VERSION}`;

const APP_SHELL_FILES = [
  '/',
  '/static/index.html',
  '/static/css/main.css',
  '/static/js/ui.js',
  '/static/js/recorder.js',
  '/static/js/progress.js',
  '/static/js/editScreen.js',
  '/static/js/pwa.js',
  '/static/js/sw/cache-manager.js',
  '/static/js/sw/queue-manager.js',
  '/static/js/sw/sync-manager.js',
  '/static/js/sw/registration.js',
  '/static/manifest.json'
];

const API_ROUTES = [
  '/api/audio/',
  '/api/sessions/',
  '/api/vault/',
  '/api/health'
];

// Install event - cache app shell
self.addEventListener('install', (event) => {
  console.log('Service Worker installing...');
  event.waitUntil(
    cacheAppShell().then(() => {
      console.log('App shell cached successfully');
      self.skipWaiting();
    })
  );
});

// Activate event - cleanup old caches
self.addEventListener('activate', (event) => {
  console.log('Service Worker activating...');
  event.waitUntil(
    cleanupOldCaches().then(() => {
      console.log('Old caches cleaned up');
      self.clients.claim();
    })
  );
});

// Fetch event - cache strategies
self.addEventListener('fetch', (event) => {
  event.respondWith(handleFetch(event.request));
});

// Background sync event
self.addEventListener('sync', (event) => {
  console.log('Background sync triggered:', event.tag);
  if (event.tag === 'dialtone-sync') {
    event.waitUntil(processQueuedRequests());
  }
});

// Cache app shell resources
async function cacheAppShell() {
  try {
    const cache = await caches.open(CACHE_NAME);
    await cache.addAll(APP_SHELL_FILES);
    console.log('App shell cached:', APP_SHELL_FILES.length, 'files');
  } catch (error) {
    console.error('Failed to cache app shell:', error);
    throw error;
  }
}

// Clean up old cache versions
async function cleanupOldCaches() {
  const cacheNames = await caches.keys();
  const oldCaches = cacheNames.filter(name => 
    name.startsWith('dialtone-') && name !== CACHE_NAME && name !== API_CACHE
  );
  
  const deletePromises = oldCaches.map(name => {
    console.log('Deleting old cache:', name);
    return caches.delete(name);
  });
  
  await Promise.all(deletePromises);
  console.log('Cleaned up', oldCaches.length, 'old caches');
}

// Handle fetch requests with cache strategies
async function handleFetch(request) {
  const url = new URL(request.url);
  
  // Handle API requests with network-first strategy
  if (isApiRequest(url.pathname)) {
    return handleApiRequest(request);
  }
  
  // Handle app shell with cache-first strategy
  if (isAppShellRequest(url.pathname)) {
    return handleAppShellRequest(request);
  }
  
  // Handle other requests with network-first fallback
  return handleGenericRequest(request);
}

// Check if request is for API
function isApiRequest(pathname) {
  return API_ROUTES.some(route => pathname.startsWith(route));
}

// Check if request is for app shell
function isAppShellRequest(pathname) {
  return APP_SHELL_FILES.some(file => 
    pathname === file || pathname === file.replace('/static', '')
  );
}

// Network-first strategy for API requests
async function handleApiRequest(request) {
  try {
    // Try network first
    const response = await fetch(request);
    
    // Cache successful responses for offline fallback
    if (response.ok) {
      const cache = await caches.open(API_CACHE);
      cache.put(request, response.clone());
    }
    
    return response;
  } catch (error) {
    console.log('Network failed for API request, trying cache:', request.url);
    
    // Try cache as fallback
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
    
    // Queue for background sync if POST/PUT
    if (request.method === 'POST' || request.method === 'PUT') {
      await queueFailedRequest(request);
      return new Response(
        JSON.stringify({ 
          error: 'Request queued for sync when online',
          queued: true 
        }),
        { 
          status: 202,
          headers: { 'Content-Type': 'application/json' }
        }
      );
    }
    
    // Return offline response for GET requests
    return createOfflineResponse(request.url);
  }
}

// Cache-first strategy for app shell
async function handleAppShellRequest(request) {
  const cachedResponse = await caches.match(request);
  
  if (cachedResponse) {
    // Update cache in background
    updateCacheInBackground(request);
    return cachedResponse;
  }
  
  // Fallback to network
  try {
    const response = await fetch(request);
    const cache = await caches.open(CACHE_NAME);
    cache.put(request, response.clone());
    return response;
  } catch (error) {
    console.error('Failed to fetch app shell resource:', request.url);
    return createOfflineResponse(request.url);
  }
}

// Generic network-first with cache fallback
async function handleGenericRequest(request) {
  try {
    return await fetch(request);
  } catch (error) {
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
    return createOfflineResponse(request.url);
  }
}

// Update cache in background (stale-while-revalidate)
async function updateCacheInBackground(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response);
    }
  } catch (error) {
    console.log('Background cache update failed:', request.url);
  }
}

// Queue failed requests for background sync
async function queueFailedRequest(request) {
  try {
    const body = await request.clone().arrayBuffer();
    const queuedRequest = {
      url: request.url,
      method: request.method,
      headers: Object.fromEntries(request.headers.entries()),
      body: Array.from(new Uint8Array(body)),
      timestamp: Date.now(),
      retryCount: 0
    };
    
    // Store in IndexedDB (simplified for now)
    const db = await openQueueDB();
    const transaction = db.transaction(['requests'], 'readwrite');
    const store = transaction.objectStore('requests');
    await store.add(queuedRequest);
    
    console.log('Request queued for background sync:', request.url);
    
    // Register for background sync
    self.registration.sync.register('dialtone-sync');
  } catch (error) {
    console.error('Failed to queue request:', error);
  }
}

// Process queued requests during background sync
async function processQueuedRequests() {
  try {
    const db = await openQueueDB();
    const transaction = db.transaction(['requests'], 'readwrite');
    const store = transaction.objectStore('requests');
    const requests = await store.getAll();
    
    for (const queuedRequest of requests) {
      try {
        // Reconstruct request
        const body = new Uint8Array(queuedRequest.body).buffer;
        const request = new Request(queuedRequest.url, {
          method: queuedRequest.method,
          headers: queuedRequest.headers,
          body: body
        });
        
        // Retry request
        const response = await fetch(request);
        
        if (response.ok) {
          // Success - remove from queue
          await store.delete(queuedRequest.id);
          console.log('Successfully synced queued request:', queuedRequest.url);
        } else {
          // Failed - update retry count
          queuedRequest.retryCount++;
          if (queuedRequest.retryCount < 3) {
            await store.put(queuedRequest);
          } else {
            await store.delete(queuedRequest.id);
            console.log('Max retries exceeded, removing:', queuedRequest.url);
          }
        }
      } catch (error) {
        console.error('Failed to sync request:', queuedRequest.url, error);
        
        // Update retry count
        queuedRequest.retryCount++;
        if (queuedRequest.retryCount < 3) {
          await store.put(queuedRequest);
        } else {
          await store.delete(queuedRequest.id);
        }
      }
    }
    
    console.log('Background sync completed');
  } catch (error) {
    console.error('Background sync failed:', error);
  }
}

// Open IndexedDB for request queue
async function openQueueDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('dialtone-queue', 1);
    
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
    
    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains('requests')) {
        const store = db.createObjectStore('requests', { 
          keyPath: 'id', 
          autoIncrement: true 
        });
        store.createIndex('timestamp', 'timestamp');
      }
    };
  });
}

// Create offline response
function createOfflineResponse(url) {
  if (url.includes('/api/')) {
    return new Response(
      JSON.stringify({ 
        error: 'Offline - request will be synced when online',
        offline: true 
      }),
      {
        status: 503,
        headers: { 'Content-Type': 'application/json' }
      }
    );
  }
  
  return new Response(
    `<!DOCTYPE html>
    <html>
    <head>
      <title>Offline - Dialtone</title>
      <style>
        body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
        .offline { color: #666; }
      </style>
    </head>
    <body>
      <h1>You're Offline</h1>
      <p class="offline">This content is not available offline.</p>
      <p>Your recordings will be saved and synced when you're back online.</p>
    </body>
    </html>`,
    {
      status: 503,
      headers: { 'Content-Type': 'text/html' }
    }
  );
}