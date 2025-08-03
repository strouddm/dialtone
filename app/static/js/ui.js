class RecorderUI {
  constructor() {
    this.recorder = null;
    this.elements = {};
    this.state = 'idle';
    
    this.bindElements();
    this.attachEventListeners();
    this.checkConnectionStatus();
  }

  bindElements() {
    this.elements = {
      recordButton: document.getElementById('recordButton'),
      pauseButton: document.getElementById('pauseButton'),
      stopButton: document.getElementById('stopButton'),
      secondaryControls: document.querySelector('.secondary-controls'),
      statusMessage: document.getElementById('statusMessage'),
      connectionStatus: document.querySelector('.connection-status'),
      errorModal: document.getElementById('errorModal'),
      errorClose: document.getElementById('errorClose'),
      progressBar: document.getElementById('progressBar')
    };
  }

  attachEventListeners() {
    if (this.elements.recordButton) {
      this.elements.recordButton.addEventListener('click', () => this.handleRecordClick());
    }
    
    if (this.elements.pauseButton) {
      this.elements.pauseButton.addEventListener('click', () => this.handlePauseClick());
    }
    
    if (this.elements.stopButton) {
      this.elements.stopButton.addEventListener('click', () => this.handleStopClick());
    }
    
    if (this.elements.errorClose) {
      this.elements.errorClose.addEventListener('click', () => this.hideError());
    }
    
    if (this.elements.errorModal) {
      this.elements.errorModal.addEventListener('click', (e) => {
        if (e.target === this.elements.errorModal) {
          this.hideError();
        }
      });
    }
    
    document.addEventListener('keydown', (e) => this.handleKeydown(e));
    
    document.addEventListener('visibilitychange', () => {
      if (document.hidden && this.state === 'recording') {
        this.handlePauseClick();
      }
    });
    
    window.addEventListener('beforeunload', () => {
      if (this.recorder) {
        this.recorder.destroy();
      }
    });
  }

  async init() {
    console.log('RecorderUI.init() called');
    try {
      this.updateConnectionStatus('connecting');
      this.updateStatus('Initializing microphone...');
      
      console.log('Creating AudioRecorder instance...');
      this.recorder = new AudioRecorder();
      console.log('Calling AudioRecorder.init()...');
      await this.recorder.init();
      console.log('AudioRecorder initialized successfully');
      
      this.updateConnectionStatus('connected');
      this.updateStatus('Ready to record');
      this.setState('ready');
      
    } catch (error) {
      console.error('RecorderUI.init() error:', error);
      this.updateConnectionStatus('error');
      this.updateStatus('Unable to access microphone');
      this.showError('Unable to access microphone. Please check your permissions and try again.');
    }
  }

  handleRecordClick() {
    switch (this.state) {
      case 'ready':
        this.startRecording();
        break;
      case 'recording':
        this.stopRecording();
        break;
      case 'paused':
        this.resumeRecording();
        break;
    }
  }

  handlePauseClick() {
    if (this.state === 'recording') {
      this.pauseRecording();
    }
  }

  handleStopClick() {
    if (this.state === 'recording' || this.state === 'paused') {
      this.stopRecording();
    }
  }

  handleKeydown(event) {
    if (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA') {
      return;
    }

    switch (event.code) {
      case 'Space':
        event.preventDefault();
        this.handleRecordClick();
        break;
      case 'KeyP':
        if (this.state === 'recording') {
          event.preventDefault();
          this.handlePauseClick();
        }
        break;
      case 'Escape':
        if (this.state === 'recording' || this.state === 'paused') {
          event.preventDefault();
          this.handleStopClick();
        } else if (!this.elements.errorModal.hidden) {
          this.hideError();
        }
        break;
    }
  }

  startRecording() {
    if (!this.recorder) return;

    if (this.recorder.startRecording()) {
      this.setState('recording');
      this.updateStatus('Recording...');
    }
  }

  pauseRecording() {
    if (!this.recorder) return;

    if (this.recorder.pauseRecording()) {
      this.setState('paused');
      this.updateStatus('Recording paused');
    }
  }

  resumeRecording() {
    if (!this.recorder) return;

    if (this.recorder.resumeRecording()) {
      this.setState('recording');
      this.updateStatus('Recording...');
    }
  }

  stopRecording() {
    if (!this.recorder) return;

    if (this.recorder.stopRecording()) {
      this.setState('processing');
      this.updateStatus('Processing recording...');
    }
  }

  setState(newState) {
    this.state = newState;
    this.updateUI();
  }

  updateUI() {
    const { recordButton, secondaryControls } = this.elements;
    
    if (!recordButton) return;

    recordButton.classList.remove('recording');
    recordButton.setAttribute('aria-pressed', 'false');
    
    switch (this.state) {
      case 'idle':
        recordButton.disabled = true;
        recordButton.setAttribute('aria-label', 'Initializing...');
        recordButton.querySelector('.record-text').textContent = 'Initializing';
        secondaryControls.hidden = true;
        break;
        
      case 'ready':
        recordButton.disabled = false;
        recordButton.setAttribute('aria-label', 'Start recording');
        recordButton.querySelector('.record-text').textContent = 'Record';
        secondaryControls.hidden = true;
        break;
        
      case 'recording':
        recordButton.disabled = false;
        recordButton.classList.add('recording');
        recordButton.setAttribute('aria-label', 'Stop recording');
        recordButton.setAttribute('aria-pressed', 'true');
        recordButton.querySelector('.record-text').textContent = 'Stop';
        secondaryControls.hidden = false;
        break;
        
      case 'paused':
        recordButton.disabled = false;
        recordButton.setAttribute('aria-label', 'Resume recording');
        recordButton.querySelector('.record-text').textContent = 'Resume';
        secondaryControls.hidden = false;
        break;
        
      case 'processing':
        recordButton.disabled = true;
        recordButton.setAttribute('aria-label', 'Processing...');
        recordButton.querySelector('.record-text').textContent = 'Processing';
        secondaryControls.hidden = true;
        break;
    }
  }

  updateStatus(message) {
    if (this.elements.statusMessage) {
      this.elements.statusMessage.textContent = message;
    }
  }

  updateConnectionStatus(status) {
    const { connectionStatus } = this.elements;
    if (!connectionStatus) return;

    connectionStatus.className = `connection-status ${status}`;
    
    const statusText = connectionStatus.querySelector('.status-text');
    if (statusText) {
      switch (status) {
        case 'connecting':
          statusText.textContent = 'Connecting...';
          break;
        case 'connected':
          statusText.textContent = 'Ready';
          break;
        case 'error':
          statusText.textContent = 'Error';
          break;
        default:
          statusText.textContent = 'Offline';
      }
    }
  }

  checkConnectionStatus() {
    const checkConnection = async () => {
      try {
        const response = await fetch('/health', {
          method: 'GET',
          cache: 'no-cache'
        });
        
        if (response.ok) {
          this.updateConnectionStatus('connected');
        } else {
          this.updateConnectionStatus('offline');
        }
      } catch (error) {
        this.updateConnectionStatus('offline');
      }
    };

    checkConnection();
    setInterval(checkConnection, 30000);
  }

  showError(message) {
    const errorModal = this.elements.errorModal;
    const errorMessage = document.getElementById('error-message');
    
    if (errorModal && errorMessage) {
      errorMessage.textContent = message;
      errorModal.hidden = false;
    }
  }

  hideError() {
    if (this.elements.errorModal) {
      this.elements.errorModal.hidden = true;
    }
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const ui = new RecorderUI();
  
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/static/sw.js').catch(error => {
      console.log('ServiceWorker registration failed:', error);
    });
  }
  
  setTimeout(() => {
    ui.init();
  }, 100);
});