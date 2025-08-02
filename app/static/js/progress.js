class ProgressIndicator {
  constructor(container, options = {}) {
    this.container = container;
    this.options = {
      showSpeed: true,
      showETA: true,
      cancelable: true,
      updateInterval: 100,
      onCancel: null,
      ...options
    };
    
    this.element = null;
    this.isActive = false;
    this.startTime = null;
    this.lastLoaded = 0;
    this.lastTime = 0;
    this.speedHistory = [];
    this.maxSpeedHistorySize = 10;
    this.lastUpdate = 0;
    
    this.init();
  }

  init() {
    this.createElement();
    this.attachEventListeners();
  }

  createElement() {
    this.element = document.createElement('div');
    this.element.className = 'upload-progress';
    this.element.setAttribute('role', 'region');
    this.element.setAttribute('aria-label', 'Upload progress');
    
    this.element.innerHTML = `
      <div class="progress-header">
        <span class="progress-percentage" aria-live="polite" aria-atomic="true">0%</span>
        ${this.options.cancelable ? 
          '<button class="progress-cancel" type="button" aria-label="Cancel upload">Cancel</button>' : 
          ''
        }
      </div>
      <div class="progress-bar-container" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0" aria-label="Upload progress">
        <div class="progress-bar-fill"></div>
      </div>
      <div class="progress-details">
        ${this.options.showSpeed ? '<span class="progress-speed" aria-label="Upload speed">0 KB/s</span>' : ''}
        ${this.options.showETA ? '<span class="progress-eta" aria-label="Time remaining">--:--</span>' : ''}
      </div>
      <div class="progress-error" hidden role="alert"></div>
    `;
    
    this.container.appendChild(this.element);
    
    this.percentageElement = this.element.querySelector('.progress-percentage');
    this.fillElement = this.element.querySelector('.progress-bar-fill');
    this.progressBarElement = this.element.querySelector('.progress-bar-container');
    this.speedElement = this.element.querySelector('.progress-speed');
    this.etaElement = this.element.querySelector('.progress-eta');
    this.errorElement = this.element.querySelector('.progress-error');
    this.cancelButton = this.element.querySelector('.progress-cancel');
  }

  attachEventListeners() {
    if (this.cancelButton && this.options.onCancel) {
      this.cancelButton.addEventListener('click', () => {
        this.handleCancel();
      });
    }
  }

  show() {
    if (this.element) {
      this.element.hidden = false;
      this.isActive = true;
      this.startTime = Date.now();
      this.lastLoaded = 0;
      this.lastTime = this.startTime;
      this.speedHistory = [];
      this.reset();
    }
  }

  hide() {
    if (this.element) {
      this.element.hidden = true;
      this.isActive = false;
    }
  }

  update(loaded, total) {
    if (!this.isActive || !this.element) return;
    
    const now = Date.now();
    
    if (now - this.lastUpdate < this.options.updateInterval) {
      return;
    }
    
    this.lastUpdate = now;
    
    const percentage = total > 0 ? Math.round((loaded / total) * 100) : 0;
    const speed = this.calculateSpeed(loaded, now);
    const eta = this.calculateETA(loaded, total, speed);
    
    this.updatePercentage(percentage);
    this.updateProgressBar(percentage);
    
    if (this.options.showSpeed) {
      this.updateSpeed(speed);
    }
    
    if (this.options.showETA) {
      this.updateETA(eta);
    }
    
    this.lastLoaded = loaded;
    this.lastTime = now;
  }

  calculateSpeed(loaded, now) {
    const timeDiff = now - this.lastTime;
    const bytesDiff = loaded - this.lastLoaded;
    
    if (timeDiff <= 0) return 0;
    
    const instantSpeed = (bytesDiff / timeDiff) * 1000;
    
    this.speedHistory.push(instantSpeed);
    if (this.speedHistory.length > this.maxSpeedHistorySize) {
      this.speedHistory.shift();
    }
    
    if (this.speedHistory.length === 0) return 0;
    
    const validSpeeds = this.speedHistory.filter(speed => speed >= 0);
    if (validSpeeds.length === 0) return 0;
    
    return validSpeeds.reduce((sum, speed) => sum + speed, 0) / validSpeeds.length;
  }

  calculateETA(loaded, total, speed) {
    if (speed <= 0 || loaded >= total) return null;
    
    const remaining = total - loaded;
    return Math.round(remaining / speed);
  }

  updatePercentage(percentage) {
    if (this.percentageElement) {
      this.percentageElement.textContent = `${percentage}%`;
    }
  }

  updateProgressBar(percentage) {
    if (this.fillElement) {
      this.fillElement.style.width = `${percentage}%`;
    }
    
    if (this.progressBarElement) {
      this.progressBarElement.setAttribute('aria-valuenow', percentage);
    }
  }

  updateSpeed(speed) {
    if (!this.speedElement) return;
    
    const formattedSpeed = this.formatBytes(speed, 1);
    this.speedElement.textContent = `${formattedSpeed}/s`;
  }

  updateETA(eta) {
    if (!this.etaElement) return;
    
    if (eta === null || eta <= 0) {
      this.etaElement.textContent = '--:--';
      return;
    }
    
    const minutes = Math.floor(eta / 60);
    const seconds = Math.floor(eta % 60);
    
    if (minutes > 99) {
      this.etaElement.textContent = '99:59+';
    } else {
      this.etaElement.textContent = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    }
  }

  formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 B';
    
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
  }

  complete() {
    this.update(100, 100);
    this.updatePercentage(100);
    this.updateProgressBar(100);
    
    if (this.speedElement) {
      this.speedElement.textContent = 'Complete';
    }
    
    if (this.etaElement) {
      this.etaElement.textContent = '00:00';
    }
    
    if (this.cancelButton) {
      this.cancelButton.disabled = true;
    }
    
    setTimeout(() => {
      this.hide();
    }, 2000);
  }

  setError(message) {
    if (this.errorElement) {
      this.errorElement.textContent = message;
      this.errorElement.hidden = false;
    }
    
    if (this.fillElement) {
      this.fillElement.style.backgroundColor = 'var(--color-danger)';
    }
    
    if (this.cancelButton) {
      this.cancelButton.textContent = 'Close';
      this.cancelButton.setAttribute('aria-label', 'Close error');
    }
    
    this.isActive = false;
  }

  handleCancel() {
    if (this.options.onCancel) {
      const confirmed = confirm('Are you sure you want to cancel the upload?');
      if (confirmed) {
        this.options.onCancel();
      }
    }
  }

  reset() {
    if (this.errorElement) {
      this.errorElement.hidden = true;
      this.errorElement.textContent = '';
    }
    
    if (this.fillElement) {
      this.fillElement.style.backgroundColor = '';
      this.fillElement.style.width = '0%';
    }
    
    if (this.progressBarElement) {
      this.progressBarElement.setAttribute('aria-valuenow', '0');
    }
    
    if (this.percentageElement) {
      this.percentageElement.textContent = '0%';
    }
    
    if (this.speedElement) {
      this.speedElement.textContent = '0 KB/s';
    }
    
    if (this.etaElement) {
      this.etaElement.textContent = '--:--';
    }
    
    if (this.cancelButton) {
      this.cancelButton.disabled = false;
      this.cancelButton.textContent = 'Cancel';
      this.cancelButton.setAttribute('aria-label', 'Cancel upload');
    }
  }

  destroy() {
    if (this.element && this.element.parentNode) {
      this.element.parentNode.removeChild(this.element);
    }
    
    this.element = null;
    this.isActive = false;
  }
}