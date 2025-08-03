export class CacheManager {
  constructor() {
    this.appShellCache = 'dialtone-shell';
    this.apiCache = 'dialtone-api';
    this.version = 'v1.0.0';
    
    // Maximum cache size (50MB)
    this.maxCacheSize = 50 * 1024 * 1024;
    
    // Cache strategy configurations
    this.strategies = {
      APP_SHELL: 'cache-first',
      API: 'network-first',
      STATIC: 'stale-while-revalidate'
    };
  }

  // Initialize cache manager
  async init() {
    try {
      await this.checkStorageQuota();
      await this.setupCaches();
      console.log('CacheManager initialized successfully');
      return true;
    } catch (error) {
      console.error('CacheManager initialization failed:', error);
      return false;
    }
  }

  // Check available storage quota
  async checkStorageQuota() {
    if ('storage' in navigator && 'estimate' in navigator.storage) {
      const estimate = await navigator.storage.estimate();
      const available = estimate.quota - estimate.usage;
      
      console.log(`Storage: ${this.formatBytes(estimate.usage)} used of ${this.formatBytes(estimate.quota)} available`);
      
      if (available < this.maxCacheSize) {
        console.warn('Limited storage available, cache operations may fail');
        await this.cleanupOldEntries();
      }
      
      return available;
    }
    return null;
  }

  // Setup initial caches
  async setupCaches() {
    const cacheNames = [this.appShellCache, this.apiCache];
    
    for (const cacheName of cacheNames) {
      if (!(await caches.has(cacheName))) {
        await caches.open(cacheName);
        console.log(`Created cache: ${cacheName}`);
      }
    }
  }

  // Cache app shell resources
  async cacheAppShell(resources) {
    const cache = await caches.open(this.appShellCache);
    
    // Cache resources individually to handle failures gracefully
    const results = await Promise.allSettled(
      resources.map(async (resource) => {
        try {
          await cache.add(resource);
          return { resource, success: true };
        } catch (error) {
          console.warn(`Failed to cache resource: ${resource}`, error);
          return { resource, success: false, error };
        }
      })
    );
    
    const successful = results.filter(r => r.value?.success).length;
    console.log(`Cached ${successful}/${resources.length} app shell resources`);
    
    return successful === resources.length;
  }

  // Handle cache-first strategy
  async handleCacheFirst(request) {
    const cachedResponse = await caches.match(request);
    
    if (cachedResponse) {
      // Update cache in background
      this.updateCacheInBackground(request);
      return cachedResponse;
    }
    
    // Fallback to network
    try {
      const response = await fetch(request);
      if (response.ok) {
        await this.cacheResponse(request, response.clone());
      }
      return response;
    } catch (error) {
      console.warn('Cache-first fallback failed:', request.url);
      throw error;
    }
  }

  // Handle network-first strategy
  async handleNetworkFirst(request) {
    try {
      const response = await fetch(request);
      
      // Cache successful responses
      if (response.ok) {
        await this.cacheResponse(request, response.clone());
      }
      
      return response;
    } catch (error) {
      // Fallback to cache
      const cachedResponse = await caches.match(request);
      if (cachedResponse) {
        console.log('Network failed, serving from cache:', request.url);
        return cachedResponse;
      }
      throw error;
    }
  }

  // Handle stale-while-revalidate strategy
  async handleStaleWhileRevalidate(request) {
    const cachedResponse = await caches.match(request);
    
    // Always try to update in background
    const networkPromise = this.updateCacheInBackground(request);
    
    if (cachedResponse) {
      return cachedResponse;
    }
    
    // If no cached version, wait for network
    try {
      return await networkPromise;
    } catch (error) {
      console.warn('Stale-while-revalidate failed:', request.url);
      throw error;
    }
  }

  // Cache a response
  async cacheResponse(request, response) {
    try {
      const cache = await this.getCacheForRequest(request);
      await cache.put(request, response);
      
      // Check cache size and cleanup if needed
      await this.enforceStorageLimits();
    } catch (error) {
      console.error('Failed to cache response:', request.url, error);
    }
  }

  // Get appropriate cache for request
  async getCacheForRequest(request) {
    const url = new URL(request.url);
    
    if (url.pathname.startsWith('/api/')) {
      return caches.open(this.apiCache);
    }
    
    return caches.open(this.appShellCache);
  }

  // Update cache in background
  async updateCacheInBackground(request) {
    try {
      const response = await fetch(request);
      
      if (response.ok) {
        await this.cacheResponse(request, response.clone());
      }
      
      return response;
    } catch (error) {
      console.log('Background cache update failed:', request.url);
      throw error;
    }
  }

  // Enforce storage limits
  async enforceStorageLimits() {
    const estimate = await navigator.storage?.estimate();
    if (!estimate) return;
    
    const usagePercent = (estimate.usage / estimate.quota) * 100;
    
    if (usagePercent > 80) {
      console.warn(`Storage usage at ${usagePercent.toFixed(1)}%, cleaning up...`);
      await this.cleanupOldEntries();
    }
  }

  // Cleanup old cache entries
  async cleanupOldEntries() {
    try {
      const cacheNames = await caches.keys();
      
      for (const cacheName of cacheNames) {
        if (cacheName.startsWith('dialtone-')) {
          await this.cleanupCache(cacheName);
        }
      }
      
      console.log('Cache cleanup completed');
    } catch (error) {
      console.error('Cache cleanup failed:', error);
    }
  }

  // Cleanup specific cache
  async cleanupCache(cacheName) {
    const cache = await caches.open(cacheName);
    const requests = await cache.keys();
    
    // Sort by timestamp (if available) or remove oldest entries
    const entries = await Promise.all(
      requests.map(async (request) => {
        const response = await cache.match(request);
        const timestamp = response?.headers.get('date') 
          ? new Date(response.headers.get('date')).getTime()
          : 0;
        return { request, timestamp };
      })
    );
    
    // Remove oldest 25% of entries
    entries.sort((a, b) => a.timestamp - b.timestamp);
    const toRemove = entries.slice(0, Math.floor(entries.length * 0.25));
    
    for (const { request } of toRemove) {
      await cache.delete(request);
    }
    
    console.log(`Cleaned up ${toRemove.length} entries from ${cacheName}`);
  }

  // Get cache statistics
  async getCacheStats() {
    const stats = {
      caches: {},
      totalSize: 0,
      totalEntries: 0
    };
    
    const cacheNames = await caches.keys();
    
    for (const cacheName of cacheNames) {
      if (cacheName.startsWith('dialtone-')) {
        const cache = await caches.open(cacheName);
        const requests = await cache.keys();
        
        stats.caches[cacheName] = {
          entries: requests.length,
          size: await this.estimateCacheSize(cache, requests)
        };
        
        stats.totalEntries += requests.length;
        stats.totalSize += stats.caches[cacheName].size;
      }
    }
    
    return stats;
  }

  // Estimate cache size
  async estimateCacheSize(cache, requests) {
    let totalSize = 0;
    
    // Sample a few responses to estimate average size
    const sampleSize = Math.min(5, requests.length);
    const samples = requests.slice(0, sampleSize);
    
    for (const request of samples) {
      try {
        const response = await cache.match(request);
        if (response) {
          const text = await response.clone().text();
          totalSize += text.length;
        }
      } catch (error) {
        console.warn('Failed to estimate size for:', request.url);
      }
    }
    
    // Extrapolate to total
    const avgSize = totalSize / sampleSize;
    return Math.round(avgSize * requests.length);
  }

  // Format bytes for display
  formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  // Clear all caches
  async clearAllCaches() {
    const cacheNames = await caches.keys();
    const dialtoneCache = cacheNames.filter(name => name.startsWith('dialtone-'));
    
    await Promise.all(dialtoneCache.map(name => caches.delete(name)));
    console.log(`Cleared ${dialtoneCache.length} caches`);
  }

  // Check cache health
  async checkCacheHealth() {
    const stats = await this.getCacheStats();
    const quota = await this.checkStorageQuota();
    
    return {
      healthy: stats.totalSize < this.maxCacheSize && quota > 0,
      stats,
      quota,
      recommendations: this.generateRecommendations(stats, quota)
    };
  }

  // Generate cache recommendations
  generateRecommendations(stats, quota) {
    const recommendations = [];
    
    if (stats.totalSize > this.maxCacheSize * 0.8) {
      recommendations.push('Consider clearing old cache entries');
    }
    
    if (quota && quota < this.maxCacheSize * 0.2) {
      recommendations.push('Low storage space available');
    }
    
    if (stats.totalEntries > 1000) {
      recommendations.push('Large number of cached entries, cleanup recommended');
    }
    
    return recommendations;
  }
}