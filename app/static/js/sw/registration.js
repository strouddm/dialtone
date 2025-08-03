// Service Worker Registration and Management

export class ServiceWorkerRegistration {
  constructor() {
    this.registration = null;
    this.updateAvailable = false;
    this.refreshing = false;
    
    // Configuration
    this.swPath = '/service-worker.js';
    this.swScope = '/';
    
    // Event handlers
    this.onUpdateAvailable = null;
    this.onControllerChange = null;
    this.onRegistrationSuccess = null;
    this.onRegistrationError = null;
  }

  // Check if service workers are supported
  isSupported() {
    return 'serviceWorker' in navigator;
  }

  // Register service worker
  async register() {
    if (!this.isSupported()) {
      console.warn('Service Worker not supported in this browser');
      return false;
    }

    try {
      console.log('Registering service worker...');
      
      this.registration = await navigator.serviceWorker.register(this.swPath, {
        scope: this.swScope
      });

      console.log('Service Worker registered successfully:', this.registration.scope);

      // Setup event listeners
      this.setupEventListeners();

      // Check for immediate updates
      await this.checkForUpdates();

      // Notify success
      if (this.onRegistrationSuccess) {
        this.onRegistrationSuccess(this.registration);
      }

      return true;
    } catch (error) {
      console.error('Service Worker registration failed:', error);
      
      if (this.onRegistrationError) {
        this.onRegistrationError(error);
      }
      
      return false;
    }
  }

  // Setup event listeners for service worker
  setupEventListeners() {
    if (!this.registration) return;

    // Listen for waiting service worker (update available)
    this.registration.addEventListener('updatefound', () => {
      console.log('Service Worker update found');
      const newWorker = this.registration.installing;
      
      if (newWorker) {
        newWorker.addEventListener('statechange', () => {
          if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
            console.log('New service worker installed, update available');
            this.updateAvailable = true;
            
            if (this.onUpdateAvailable) {
              this.onUpdateAvailable(newWorker);
            }
            
            this.showUpdateNotification();
          }
        });
      }
    });

    // Listen for controller changes (new SW taking control)
    navigator.serviceWorker.addEventListener('controllerchange', () => {
      console.log('Service Worker controller changed');
      
      if (!this.refreshing) {
        console.log('Refreshing page for new service worker');
        this.refreshing = true;
        window.location.reload();
      }
      
      if (this.onControllerChange) {
        this.onControllerChange();
      }
    });

    // Listen for messages from service worker
    navigator.serviceWorker.addEventListener('message', (event) => {
      this.handleServiceWorkerMessage(event);
    });
  }

  // Check for service worker updates
  async checkForUpdates() {
    if (!this.registration) return false;

    try {
      await this.registration.update();
      console.log('Checked for service worker updates');
      return true;
    } catch (error) {
      console.error('Failed to check for updates:', error);
      return false;
    }
  }

  // Skip waiting and activate new service worker
  async skipWaiting() {
    if (!this.registration || !this.registration.waiting) {
      console.warn('No waiting service worker to activate');
      return false;
    }

    try {
      // Send skip waiting message to service worker
      this.registration.waiting.postMessage({ type: 'SKIP_WAITING' });
      console.log('Sent skip waiting message to service worker');
      return true;
    } catch (error) {
      console.error('Failed to skip waiting:', error);
      return false;
    }
  }

  // Handle messages from service worker
  handleServiceWorkerMessage(event) {
    const { data } = event;
    
    console.log('Message from service worker:', data);
    
    switch (data.type) {
      case 'SW_UPDATED':
        this.handleServiceWorkerUpdated();
        break;
        
      case 'CACHE_UPDATED':
        this.handleCacheUpdated(data);
        break;
        
      case 'OFFLINE_READY':
        this.handleOfflineReady();
        break;
        
      default:
        console.log('Unknown service worker message type:', data.type);
    }
  }

  // Handle service worker updated
  handleServiceWorkerUpdated() {
    console.log('Service worker has been updated');
    this.showUpdateSuccessNotification();
  }

  // Handle cache updated
  handleCacheUpdated(data) {
    console.log('Cache updated:', data);
  }

  // Handle offline ready
  handleOfflineReady() {
    console.log('App is ready to work offline');
    this.showOfflineReadyNotification();
  }

  // Show update notification
  showUpdateNotification() {
    const notification = this.createUpdateNotification();
    document.body.appendChild(notification);
    
    // Auto-hide after 10 seconds if not interacted with
    setTimeout(() => {
      if (notification.parentNode) {
        this.hideNotification(notification);
      }
    }, 10000);
  }

  // Create update notification element
  createUpdateNotification() {
    const notification = document.createElement('div');
    notification.className = 'sw-update-notification';
    notification.innerHTML = `
      <div class="notification-content">
        <div class="notification-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/>
          </svg>
        </div>
        <div class="notification-text">
          <div class="notification-title">Update Available</div>
          <div class="notification-message">A new version of Dialtone is ready to install</div>
        </div>
        <div class="notification-actions">
          <button class="btn-update">Update</button>
          <button class="btn-dismiss">Later</button>
        </div>
      </div>
    `;

    // Add event listeners
    const updateBtn = notification.querySelector('.btn-update');
    const dismissBtn = notification.querySelector('.btn-dismiss');

    updateBtn.addEventListener('click', () => {
      this.activateUpdate();
      this.hideNotification(notification);
    });

    dismissBtn.addEventListener('click', () => {
      this.hideNotification(notification);
    });

    return notification;
  }

  // Show offline ready notification
  showOfflineReadyNotification() {
    const notification = this.createInfoNotification(
      'Ready for Offline',
      'Dialtone is now ready to work offline'
    );
    
    document.body.appendChild(notification);
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
      this.hideNotification(notification);
    }, 5000);
  }

  // Show update success notification
  showUpdateSuccessNotification() {
    const notification = this.createInfoNotification(
      'Update Complete',
      'Dialtone has been updated to the latest version'
    );
    
    document.body.appendChild(notification);
    
    // Auto-hide after 3 seconds
    setTimeout(() => {
      this.hideNotification(notification);
    }, 3000);
  }

  // Create info notification
  createInfoNotification(title, message) {
    const notification = document.createElement('div');
    notification.className = 'sw-info-notification';
    notification.innerHTML = `
      <div class="notification-content">
        <div class="notification-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
            <polyline points="22,4 12,14.01 9,11.01"/>
          </svg>
        </div>
        <div class="notification-text">
          <div class="notification-title">${title}</div>
          <div class="notification-message">${message}</div>
        </div>
        <button class="btn-close">×</button>
      </div>
    `;

    // Add close event listener
    const closeBtn = notification.querySelector('.btn-close');
    closeBtn.addEventListener('click', () => {
      this.hideNotification(notification);
    });

    return notification;
  }

  // Hide notification with animation
  hideNotification(notification) {
    notification.style.opacity = '0';
    notification.style.transform = 'translateY(-100%)';
    
    setTimeout(() => {
      if (notification.parentNode) {
        notification.parentNode.removeChild(notification);
      }
    }, 300);
  }

  // Activate waiting service worker
  async activateUpdate() {
    if (!this.updateAvailable || !this.registration.waiting) {
      console.warn('No update available to activate');
      return false;
    }

    try {
      console.log('Activating service worker update...');
      await this.skipWaiting();
      return true;
    } catch (error) {
      console.error('Failed to activate update:', error);
      return false;
    }
  }

  // Unregister service worker
  async unregister() {
    if (!this.registration) {
      console.warn('No service worker registration to unregister');
      return false;
    }

    try {
      const result = await this.registration.unregister();
      console.log('Service worker unregistered:', result);
      
      this.registration = null;
      this.updateAvailable = false;
      
      return result;
    } catch (error) {
      console.error('Failed to unregister service worker:', error);
      return false;
    }
  }

  // Get registration status
  getStatus() {
    if (!this.isSupported()) {
      return {
        supported: false,
        registered: false,
        updateAvailable: false,
        scope: null
      };
    }

    return {
      supported: true,
      registered: !!this.registration,
      updateAvailable: this.updateAvailable,
      scope: this.registration?.scope || null,
      active: !!navigator.serviceWorker.controller
    };
  }

  // Send message to service worker
  async sendMessage(message) {
    if (!navigator.serviceWorker.controller) {
      console.warn('No active service worker to send message to');
      return false;
    }

    try {
      navigator.serviceWorker.controller.postMessage(message);
      return true;
    } catch (error) {
      console.error('Failed to send message to service worker:', error);
      return false;
    }
  }

  // Wait for service worker to be ready
  async waitForReady() {
    if (!this.isSupported()) {
      throw new Error('Service Worker not supported');
    }

    return await navigator.serviceWorker.ready;
  }
}

// Export registration function for direct use
export async function registerServiceWorker() {
  const swRegistration = new ServiceWorkerRegistration();
  
  // Setup callbacks for better user experience
  swRegistration.onUpdateAvailable = (newWorker) => {
    console.log('Update available callback triggered');
  };
  
  swRegistration.onRegistrationSuccess = (registration) => {
    console.log('Registration success callback triggered');
  };
  
  swRegistration.onRegistrationError = (error) => {
    console.error('Registration error callback triggered:', error);
  };
  
  return await swRegistration.register();
}

// Export class for advanced usage
export default ServiceWorkerRegistration;