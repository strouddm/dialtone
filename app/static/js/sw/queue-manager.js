export class QueueManager {
  constructor() {
    this.dbName = 'dialtone-queue';
    this.version = 1;
    this.storeName = 'requests';
    
    // Retry configuration
    this.maxRetries = 3;
    this.retryDelays = [1000, 5000, 15000]; // 1s, 5s, 15s
    
    // Storage limits
    this.maxQueueSize = 100;
    this.maxRequestAge = 7 * 24 * 60 * 60 * 1000; // 7 days
  }

  // Initialize queue manager
  async init() {
    try {
      await this.openDB();
      await this.cleanupOldRequests();
      console.log('QueueManager initialized successfully');
      return true;
    } catch (error) {
      console.error('QueueManager initialization failed:', error);
      return false;
    }
  }

  // Open IndexedDB connection
  async openDB() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(this.dbName, this.version);
      
      request.onerror = () => {
        console.error('Failed to open IndexedDB:', request.error);
        reject(request.error);
      };
      
      request.onsuccess = () => {
        console.log('IndexedDB opened successfully');
        resolve(request.result);
      };
      
      request.onupgradeneeded = (event) => {
        const db = event.target.result;
        
        // Create requests store
        if (!db.objectStoreNames.contains(this.storeName)) {
          const store = db.createObjectStore(this.storeName, {
            keyPath: 'id',
            autoIncrement: true
          });
          
          // Create indexes
          store.createIndex('timestamp', 'timestamp');
          store.createIndex('url', 'url');
          store.createIndex('retryCount', 'retryCount');
          store.createIndex('status', 'status');
          
          console.log('Created requests object store with indexes');
        }
      };
    });
  }

  // Queue a failed request
  async queueRequest(request, data = null) {
    try {
      // Check queue size before adding
      const queueSize = await this.getQueueSize();
      if (queueSize >= this.maxQueueSize) {
        console.warn('Queue is full, removing oldest entry');
        await this.removeOldestEntry();
      }
      
      // Prepare request data
      let body = null;
      if (data) {
        body = data;
      } else if (request.body) {
        // Convert request body to storable format
        body = await this.serializeRequestBody(request);
      }
      
      const queuedRequest = {
        url: request.url,
        method: request.method,
        headers: Object.fromEntries(request.headers.entries()),
        body: body,
        timestamp: Date.now(),
        retryCount: 0,
        status: 'queued',
        lastError: null,
        nextRetry: Date.now() + this.retryDelays[0]
      };
      
      const db = await this.openDB();
      const transaction = db.transaction([this.storeName], 'readwrite');
      const store = transaction.objectStore(this.storeName);
      
      const result = await new Promise((resolve, reject) => {
        const request = store.add(queuedRequest);
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
      });
      
      console.log('Request queued successfully:', queuedRequest.url, 'ID:', result);
      
      // Notify about queued request
      await this.notifyQueueUpdate();
      
      return result;
    } catch (error) {
      console.error('Failed to queue request:', error);
      throw error;
    }
  }

  // Process all queued requests
  async processQueue() {
    try {
      const queuedRequests = await this.getQueuedRequests();
      
      if (queuedRequests.length === 0) {
        console.log('No requests in queue to process');
        return { success: 0, failed: 0, total: 0 };
      }
      
      console.log(`Processing ${queuedRequests.length} queued requests`);
      
      let success = 0;
      let failed = 0;
      
      for (const queuedRequest of queuedRequests) {
        try {
          if (await this.shouldRetryRequest(queuedRequest)) {
            const result = await this.retryRequest(queuedRequest);
            if (result) {
              success++;
              await this.removeRequest(queuedRequest.id);
            } else {
              failed++;
              await this.updateRequestRetry(queuedRequest);
            }
          }
        } catch (error) {
          console.error('Error processing queued request:', queuedRequest.url, error);
          failed++;
          await this.updateRequestError(queuedRequest, error);
        }
      }
      
      console.log(`Queue processing complete: ${success} success, ${failed} failed`);
      
      // Notify about queue update
      await this.notifyQueueUpdate();
      
      return { success, failed, total: queuedRequests.length };
    } catch (error) {
      console.error('Queue processing failed:', error);
      throw error;
    }
  }

  // Get all queued requests
  async getQueuedRequests() {
    const db = await this.openDB();
    const transaction = db.transaction([this.storeName], 'readonly');
    const store = transaction.objectStore(this.storeName);
    
    return new Promise((resolve, reject) => {
      const request = store.getAll();
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  // Get queued requests ready for retry
  async getRetryableRequests() {
    const allRequests = await this.getQueuedRequests();
    const now = Date.now();
    
    return allRequests.filter(req => 
      req.status === 'queued' && 
      req.retryCount < this.maxRetries &&
      req.nextRetry <= now
    );
  }

  // Check if request should be retried
  shouldRetryRequest(queuedRequest) {
    const now = Date.now();
    return queuedRequest.retryCount < this.maxRetries && 
           queuedRequest.nextRetry <= now &&
           queuedRequest.status === 'queued';
  }

  // Retry a specific request
  async retryRequest(queuedRequest) {
    try {
      // Reconstruct the request
      const request = await this.reconstructRequest(queuedRequest);
      
      // Make the request
      const response = await fetch(request);
      
      if (response.ok) {
        console.log('Request retry successful:', queuedRequest.url);
        return true;
      } else {
        console.warn('Request retry failed with status:', response.status, queuedRequest.url);
        return false;
      }
    } catch (error) {
      console.warn('Request retry failed:', queuedRequest.url, error);
      return false;
    }
  }

  // Reconstruct request from queued data
  async reconstructRequest(queuedRequest) {
    const options = {
      method: queuedRequest.method,
      headers: queuedRequest.headers
    };
    
    if (queuedRequest.body) {
      options.body = await this.deserializeRequestBody(queuedRequest.body);
    }
    
    return new Request(queuedRequest.url, options);
  }

  // Serialize request body for storage
  async serializeRequestBody(request) {
    try {
      const contentType = request.headers.get('content-type') || '';
      
      if (contentType.includes('application/json')) {
        return {
          type: 'json',
          data: await request.text()
        };
      } else if (contentType.includes('multipart/form-data')) {
        // For FormData, we need to reconstruct it differently
        const formData = await request.formData();
        const entries = [];
        
        for (const [key, value] of formData.entries()) {
          if (value instanceof File) {
            entries.push({
              key,
              type: 'file',
              name: value.name,
              size: value.size,
              lastModified: value.lastModified,
              data: await this.fileToBase64(value)
            });
          } else {
            entries.push({
              key,
              type: 'string',
              value
            });
          }
        }
        
        return {
          type: 'formdata',
          entries
        };
      } else {
        return {
          type: 'text',
          data: await request.text()
        };
      }
    } catch (error) {
      console.error('Failed to serialize request body:', error);
      return null;
    }
  }

  // Deserialize request body from storage
  async deserializeRequestBody(serializedBody) {
    try {
      switch (serializedBody.type) {
        case 'json':
          return serializedBody.data;
          
        case 'formdata':
          const formData = new FormData();
          
          for (const entry of serializedBody.entries) {
            if (entry.type === 'file') {
              const file = await this.base64ToFile(
                entry.data,
                entry.name,
                entry.lastModified
              );
              formData.append(entry.key, file);
            } else {
              formData.append(entry.key, entry.value);
            }
          }
          
          return formData;
          
        case 'text':
        default:
          return serializedBody.data;
      }
    } catch (error) {
      console.error('Failed to deserialize request body:', error);
      return null;
    }
  }

  // Convert file to base64
  async fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  // Convert base64 to file
  async base64ToFile(base64Data, filename, lastModified) {
    const response = await fetch(base64Data);
    const blob = await response.blob();
    return new File([blob], filename, { lastModified });
  }

  // Update request retry information
  async updateRequestRetry(queuedRequest) {
    queuedRequest.retryCount++;
    queuedRequest.lastRetry = Date.now();
    
    if (queuedRequest.retryCount < this.maxRetries) {
      const delay = this.retryDelays[queuedRequest.retryCount - 1] || this.retryDelays[this.retryDelays.length - 1];
      queuedRequest.nextRetry = Date.now() + delay;
      queuedRequest.status = 'queued';
    } else {
      queuedRequest.status = 'failed';
      queuedRequest.nextRetry = null;
    }
    
    await this.updateRequest(queuedRequest);
  }

  // Update request with error information
  async updateRequestError(queuedRequest, error) {
    queuedRequest.lastError = error.message;
    queuedRequest.retryCount++;
    
    if (queuedRequest.retryCount >= this.maxRetries) {
      queuedRequest.status = 'failed';
    }
    
    await this.updateRequest(queuedRequest);
  }

  // Update request in database
  async updateRequest(queuedRequest) {
    const db = await this.openDB();
    const transaction = db.transaction([this.storeName], 'readwrite');
    const store = transaction.objectStore(this.storeName);
    
    return new Promise((resolve, reject) => {
      const request = store.put(queuedRequest);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  // Remove request from queue
  async removeRequest(id) {
    const db = await this.openDB();
    const transaction = db.transaction([this.storeName], 'readwrite');
    const store = transaction.objectStore(this.storeName);
    
    return new Promise((resolve, reject) => {
      const request = store.delete(id);
      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });
  }

  // Get queue size
  async getQueueSize() {
    const db = await this.openDB();
    const transaction = db.transaction([this.storeName], 'readonly');
    const store = transaction.objectStore(this.storeName);
    
    return new Promise((resolve, reject) => {
      const request = store.count();
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  // Remove oldest entry from queue
  async removeOldestEntry() {
    const db = await this.openDB();
    const transaction = db.transaction([this.storeName], 'readwrite');
    const store = transaction.objectStore(this.storeName);
    const index = store.index('timestamp');
    
    return new Promise((resolve, reject) => {
      const request = index.openCursor();
      
      request.onsuccess = (event) => {
        const cursor = event.target.result;
        if (cursor) {
          cursor.delete();
          resolve();
        } else {
          resolve();
        }
      };
      
      request.onerror = () => reject(request.error);
    });
  }

  // Cleanup old requests
  async cleanupOldRequests() {
    const cutoff = Date.now() - this.maxRequestAge;
    const db = await this.openDB();
    const transaction = db.transaction([this.storeName], 'readwrite');
    const store = transaction.objectStore(this.storeName);
    const index = store.index('timestamp');
    
    let deletedCount = 0;
    
    return new Promise((resolve, reject) => {
      const range = IDBKeyRange.upperBound(cutoff);
      const request = index.openCursor(range);
      
      request.onsuccess = (event) => {
        const cursor = event.target.result;
        if (cursor) {
          cursor.delete();
          deletedCount++;
          cursor.continue();
        } else {
          if (deletedCount > 0) {
            console.log(`Cleaned up ${deletedCount} old queued requests`);
          }
          resolve(deletedCount);
        }
      };
      
      request.onerror = () => reject(request.error);
    });
  }

  // Get queue statistics
  async getQueueStats() {
    const requests = await this.getQueuedRequests();
    
    const stats = {
      total: requests.length,
      queued: 0,
      failed: 0,
      retrying: 0,
      oldestRequest: null,
      newestRequest: null
    };
    
    for (const req of requests) {
      switch (req.status) {
        case 'queued':
          if (req.retryCount > 0) {
            stats.retrying++;
          } else {
            stats.queued++;
          }
          break;
        case 'failed':
          stats.failed++;
          break;
      }
      
      if (!stats.oldestRequest || req.timestamp < stats.oldestRequest) {
        stats.oldestRequest = req.timestamp;
      }
      
      if (!stats.newestRequest || req.timestamp > stats.newestRequest) {
        stats.newestRequest = req.timestamp;
      }
    }
    
    return stats;
  }

  // Clear all queued requests
  async clearQueue() {
    const db = await this.openDB();
    const transaction = db.transaction([this.storeName], 'readwrite');
    const store = transaction.objectStore(this.storeName);
    
    return new Promise((resolve, reject) => {
      const request = store.clear();
      request.onsuccess = () => {
        console.log('Queue cleared successfully');
        resolve();
      };
      request.onerror = () => reject(request.error);
    });
  }

  // Notify about queue updates
  async notifyQueueUpdate() {
    if ('serviceWorker' in navigator && navigator.serviceWorker.controller) {
      navigator.serviceWorker.controller.postMessage({
        type: 'QUEUE_UPDATE',
        timestamp: Date.now()
      });
    }
  }
}