export class SyncManager {
  constructor(queueManager) {
    this.queueManager = queueManager;
    this.syncTag = 'dialtone-sync';
    this.periodicSyncTag = 'dialtone-periodic-sync';
    
    // Sync configuration
    this.syncInterval = 30000; // 30 seconds
    this.maxSyncRetries = 3;
    this.syncTimeout = 60000; // 60 seconds
    
    // Event listeners
    this.setupEventListeners();
  }

  // Initialize sync manager
  async init() {
    try {
      await this.registerBackgroundSync();
      await this.setupPeriodicSync();
      console.log('SyncManager initialized successfully');
      return true;
    } catch (error) {
      console.error('SyncManager initialization failed:', error);
      return false;
    }
  }

  // Setup event listeners
  setupEventListeners() {
    // Listen for online/offline events
    window.addEventListener('online', () => {
      console.log('Device came online, triggering sync');
      this.triggerSync();
    });

    window.addEventListener('offline', () => {
      console.log('Device went offline');
      this.handleOfflineState();
    });

    // Listen for visibility change
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden && navigator.onLine) {
        console.log('App became visible while online, checking for pending sync');
        this.checkPendingSync();
      }
    });

    // Listen for service worker messages
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.addEventListener('message', (event) => {
        this.handleServiceWorkerMessage(event);
      });
    }
  }

  // Register background sync
  async registerBackgroundSync() {
    if (!('serviceWorker' in navigator) || !('sync' in window.ServiceWorkerRegistration.prototype)) {
      console.warn('Background Sync not supported, using fallback strategy');
      this.setupFallbackSync();
      return false;
    }

    try {
      const registration = await navigator.serviceWorker.ready;
      await registration.sync.register(this.syncTag);
      console.log('Background sync registered successfully');
      return true;
    } catch (error) {
      console.error('Failed to register background sync:', error);
      this.setupFallbackSync();
      return false;
    }
  }

  // Setup periodic sync (for supported browsers)
  async setupPeriodicSync() {
    if (!('serviceWorker' in navigator) || !('periodicSync' in window.ServiceWorkerRegistration.prototype)) {
      console.log('Periodic Background Sync not supported');
      return false;
    }

    try {
      const registration = await navigator.serviceWorker.ready;
      const status = await navigator.permissions.query({ name: 'periodic-background-sync' });
      
      if (status.state === 'granted') {
        await registration.periodicSync.register(this.periodicSyncTag, {
          minInterval: this.syncInterval
        });
        console.log('Periodic background sync registered');
        return true;
      } else {
        console.log('Periodic background sync permission not granted');
        return false;
      }
    } catch (error) {
      console.error('Failed to setup periodic sync:', error);
      return false;
    }
  }

  // Setup fallback sync for unsupported browsers
  setupFallbackSync() {
    console.log('Setting up fallback sync strategy');
    
    // Periodic check when online
    setInterval(() => {
      if (navigator.onLine) {
        this.checkAndSync();
      }
    }, this.syncInterval);

    // Manual sync on user interaction
    this.showManualSyncOption();
  }

  // Trigger immediate sync
  async triggerSync() {
    try {
      // First try background sync
      if ('serviceWorker' in navigator && 'sync' in window.ServiceWorkerRegistration.prototype) {
        const registration = await navigator.serviceWorker.ready;
        await registration.sync.register(this.syncTag);
        console.log('Background sync triggered');
      } else {
        // Fallback to immediate sync
        await this.performImmediateSync();
      }
    } catch (error) {
      console.error('Failed to trigger sync:', error);
      // Try immediate sync as fallback
      await this.performImmediateSync();
    }
  }

  // Perform immediate sync
  async performImmediateSync() {
    if (!navigator.onLine) {
      console.log('Device is offline, cannot perform immediate sync');
      return false;
    }

    try {
      console.log('Performing immediate sync...');
      this.showSyncStatus('syncing');
      
      const result = await this.queueManager.processQueue();
      
      if (result.total > 0) {
        console.log(`Sync completed: ${result.success} success, ${result.failed} failed`);
        this.showSyncStatus('completed', result);
        
        // Notify user about sync results
        this.notifyUser(result);
      } else {
        console.log('No pending requests to sync');
        this.showSyncStatus('idle');
      }
      
      return true;
    } catch (error) {
      console.error('Immediate sync failed:', error);
      this.showSyncStatus('error', { error: error.message });
      return false;
    }
  }

  // Check for pending sync
  async checkPendingSync() {
    const stats = await this.queueManager.getQueueStats();
    
    if (stats.total > 0) {
      console.log(`Found ${stats.total} pending requests, triggering sync`);
      await this.triggerSync();
    }
  }

  // Check and sync if needed
  async checkAndSync() {
    const stats = await this.queueManager.getQueueStats();
    
    if (stats.total > 0 && navigator.onLine) {
      await this.performImmediateSync();
    }
  }

  // Handle offline state
  handleOfflineState() {
    this.showSyncStatus('offline');
    this.showOfflineIndicator();
  }

  // Handle service worker messages
  handleServiceWorkerMessage(event) {
    const { data } = event;
    
    switch (data.type) {
      case 'SYNC_COMPLETE':
        this.handleSyncComplete(data.result);
        break;
        
      case 'SYNC_ERROR':
        this.handleSyncError(data.error);
        break;
        
      case 'QUEUE_UPDATE':
        this.handleQueueUpdate();
        break;
        
      default:
        console.log('Unknown service worker message:', data);
    }
  }

  // Handle sync completion
  handleSyncComplete(result) {
    console.log('Background sync completed:', result);
    this.showSyncStatus('completed', result);
    this.notifyUser(result);
  }

  // Handle sync error
  handleSyncError(error) {
    console.error('Background sync error:', error);
    this.showSyncStatus('error', { error });
    this.showManualSyncOption();
  }

  // Handle queue updates
  async handleQueueUpdate() {
    const stats = await this.queueManager.getQueueStats();
    this.updateSyncIndicator(stats);
  }

  // Show sync status
  showSyncStatus(status, data = {}) {
    const syncIndicator = this.getSyncIndicator();
    
    if (!syncIndicator) return;
    
    // Remove existing status classes
    syncIndicator.classList.remove('syncing', 'completed', 'error', 'offline', 'idle');
    
    // Add current status class
    syncIndicator.classList.add(status);
    
    // Update indicator content
    this.updateSyncIndicatorContent(syncIndicator, status, data);
    
    // Show indicator if it was hidden
    syncIndicator.style.display = 'flex';
    
    // Auto-hide after success
    if (status === 'completed') {
      setTimeout(() => {
        if (syncIndicator.classList.contains('completed')) {
          syncIndicator.style.display = 'none';
        }
      }, 3000);
    }
  }

  // Update sync indicator content
  updateSyncIndicatorContent(indicator, status, data) {
    const icon = indicator.querySelector('.sync-icon');
    const text = indicator.querySelector('.sync-text');
    
    if (!icon || !text) return;
    
    switch (status) {
      case 'syncing':
        icon.innerHTML = this.getSpinnerIcon();
        text.textContent = 'Syncing...';
        break;
        
      case 'completed':
        icon.innerHTML = this.getCheckIcon();
        if (data.total > 0) {
          text.textContent = `Synced ${data.success} of ${data.total} recordings`;
        } else {
          text.textContent = 'All synced';
        }
        break;
        
      case 'error':
        icon.innerHTML = this.getErrorIcon();
        text.textContent = 'Sync failed';
        break;
        
      case 'offline':
        icon.innerHTML = this.getOfflineIcon();
        text.textContent = 'Offline';
        break;
        
      case 'idle':
      default:
        indicator.style.display = 'none';
        break;
    }
  }

  // Get or create sync indicator
  getSyncIndicator() {
    let indicator = document.getElementById('sync-indicator');
    
    if (!indicator) {
      indicator = this.createSyncIndicator();
      document.body.appendChild(indicator);
    }
    
    return indicator;
  }

  // Create sync indicator element
  createSyncIndicator() {
    const indicator = document.createElement('div');
    indicator.id = 'sync-indicator';
    indicator.className = 'sync-indicator';
    indicator.innerHTML = `
      <div class="sync-icon"></div>
      <div class="sync-text"></div>
      <button class="sync-retry" style="display: none;">Retry</button>
    `;
    
    // Add retry functionality
    const retryButton = indicator.querySelector('.sync-retry');
    retryButton.addEventListener('click', () => {
      this.triggerSync();
    });
    
    return indicator;
  }

  // Show offline indicator
  showOfflineIndicator() {
    const indicator = this.getSyncIndicator();
    const retryButton = indicator.querySelector('.sync-retry');
    
    if (retryButton) {
      retryButton.style.display = 'none';
    }
  }

  // Show manual sync option
  showManualSyncOption() {
    const indicator = this.getSyncIndicator();
    const retryButton = indicator.querySelector('.sync-retry');
    
    if (retryButton && navigator.onLine) {
      retryButton.style.display = 'inline-block';
      retryButton.textContent = 'Retry Sync';
    }
  }

  // Update sync indicator with queue stats
  async updateSyncIndicator(stats) {
    const indicator = this.getSyncIndicator();
    
    if (stats.total > 0) {
      indicator.style.display = 'flex';
      
      const text = indicator.querySelector('.sync-text');
      if (text) {
        text.textContent = `${stats.total} pending`;
      }
      
      // Show manual sync option if online
      if (navigator.onLine) {
        this.showManualSyncOption();
      }
    } else {
      indicator.style.display = 'none';
    }
  }

  // Notify user about sync results
  notifyUser(result) {
    if ('Notification' in window && Notification.permission === 'granted') {
      if (result.success > 0) {
        new Notification('Dialtone Sync Complete', {
          body: `Successfully synced ${result.success} recordings`,
          icon: '/static/assets/icons/icon-192x192.png',
          tag: 'dialtone-sync'
        });
      } else if (result.failed > 0) {
        new Notification('Dialtone Sync Issues', {
          body: `Failed to sync ${result.failed} recordings`,
          icon: '/static/assets/icons/icon-192x192.png',
          tag: 'dialtone-sync'
        });
      }
    }
  }

  // Request notification permission
  async requestNotificationPermission() {
    if ('Notification' in window && Notification.permission === 'default') {
      const permission = await Notification.requestPermission();
      console.log('Notification permission:', permission);
      return permission === 'granted';
    }
    return Notification.permission === 'granted';
  }

  // Icon helpers
  getSpinnerIcon() {
    return `
      <svg class="spinner" width="16" height="16" viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2" fill="none" stroke-dasharray="32" stroke-dashoffset="32">
          <animate attributeName="stroke-dasharray" dur="1s" values="0 32;16 16;0 32;0 32" repeatCount="indefinite"/>
          <animate attributeName="stroke-dashoffset" dur="1s" values="0;-16;-32;-32" repeatCount="indefinite"/>
        </circle>
      </svg>
    `;
  }

  getCheckIcon() {
    return `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M20 6L9 17l-5-5"/>
      </svg>
    `;
  }

  getErrorIcon() {
    return `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"/>
        <line x1="15" y1="9" x2="9" y2="15"/>
        <line x1="9" y1="9" x2="15" y2="15"/>
      </svg>
    `;
  }

  getOfflineIcon() {
    return `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M5.5 9.5l13 13M1 7l4.5 4.5M9 1l4.5 4.5M23 17l-4.5-4.5M15 23l-4.5-4.5"/>
      </svg>
    `;
  }

  // Get sync statistics
  async getSyncStats() {
    const queueStats = await this.queueManager.getQueueStats();
    
    return {
      queueStats,
      online: navigator.onLine,
      backgroundSyncSupported: 'serviceWorker' in navigator && 'sync' in window.ServiceWorkerRegistration.prototype,
      periodicSyncSupported: 'serviceWorker' in navigator && 'periodicSync' in window.ServiceWorkerRegistration.prototype,
      lastSync: localStorage.getItem('dialtone-last-sync'),
      syncInterval: this.syncInterval
    };
  }

  // Manual sync for testing
  async manualSync() {
    console.log('Manual sync triggered');
    return await this.performImmediateSync();
  }

  // Clear sync history
  clearSyncHistory() {
    localStorage.removeItem('dialtone-last-sync');
    console.log('Sync history cleared');
  }
}