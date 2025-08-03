class AudioRecorder {
  constructor() {
    this.mediaRecorder = null;
    this.audioChunks = [];
    this.startTime = null;
    this.timerInterval = null;
    this.stream = null;
    this.isRecording = false;
    this.isPaused = false;
    this.visualizer = null;
    this.analysisContext = null;
    
    this.supportedMimeTypes = [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/mp4',
      'audio/ogg;codecs=opus'
    ];
  }

  async init() {
    console.log('AudioRecorder.init() called');
    if (!this.checkBrowserSupport()) {
      console.error('Browser support check failed');
      throw new Error('Audio recording is not supported in this browser');
    }
    console.log('Browser support check passed');

    try {
      console.log('Requesting microphone access...');
      this.stream = await this.requestMicrophone();
      console.log('Microphone access granted, stream:', this.stream);
      
      console.log('Setting up recorder...');
      this.setupRecorder();
      console.log('Recorder setup complete');
      
      console.log('Setting up audio visualization...');
      this.setupAudioVisualization();
      console.log('Audio visualization setup complete');
      
      return true;
    } catch (error) {
      console.error('AudioRecorder.init() error:', error.name, error.message, error);
      this.handleError(error);
      throw error;
    }
  }

  checkBrowserSupport() {
    console.log('Checking browser support...');
    console.log('navigator.mediaDevices:', !!navigator.mediaDevices);
    console.log('getUserMedia:', !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia));
    console.log('MediaRecorder:', !!window.MediaRecorder);
    console.log('HTTPS:', location.protocol === 'https:');
    console.log('User Agent:', navigator.userAgent);
    
    const supported = !!(navigator.mediaDevices && 
              navigator.mediaDevices.getUserMedia && 
              window.MediaRecorder);
              
    console.log('Browser support result:', supported);
    return supported;
  }

  async requestMicrophone() {
    const constraints = {
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        sampleRate: 16000
      }
    };

    console.log('Requesting getUserMedia with constraints:', constraints);
    try {
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      console.log('getUserMedia successful, tracks:', stream.getTracks());
      return stream;
    } catch (error) {
      console.error('getUserMedia failed:', error.name, error.message);
      throw error;
    }
  }

  setupRecorder() {
    const mimeType = this.getSupportedMimeType();
    console.log('Supported MIME type:', mimeType);
    const options = mimeType ? { mimeType } : {};
    
    console.log('Creating MediaRecorder with options:', options);
    try {
      this.mediaRecorder = new MediaRecorder(this.stream, options);
      console.log('MediaRecorder created successfully');
    } catch (error) {
      console.error('MediaRecorder creation failed:', error.name, error.message);
      throw error;
    }
    
    this.mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        this.audioChunks.push(event.data);
      }
    };

    this.mediaRecorder.onstop = () => {
      this.processRecording();
    };

    this.mediaRecorder.onerror = (event) => {
      console.error('MediaRecorder error:', event);
      this.handleError(new Error('Recording failed'));
    };
  }

  getSupportedMimeType() {
    return this.supportedMimeTypes.find(type => MediaRecorder.isTypeSupported(type));
  }

  setupAudioVisualization() {
    try {
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const analyser = audioContext.createAnalyser();
      const source = audioContext.createMediaStreamSource(this.stream);
      
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.8;
      source.connect(analyser);
      
      this.analysisContext = {
        audioContext,
        analyser,
        dataArray: new Uint8Array(analyser.frequencyBinCount)
      };
    } catch (error) {
      console.warn('Audio visualization not available:', error);
    }
  }

  startRecording() {
    if (!this.mediaRecorder || this.isRecording) {
      return false;
    }

    try {
      this.audioChunks = [];
      this.startTime = Date.now();
      this.isRecording = true;
      this.isPaused = false;
      
      this.mediaRecorder.start(1000);
      this.startTimer();
      this.startVisualization();
      
      return true;
    } catch (error) {
      this.handleError(error);
      return false;
    }
  }

  pauseRecording() {
    if (!this.isRecording || this.isPaused) {
      return false;
    }

    try {
      this.mediaRecorder.pause();
      this.isPaused = true;
      this.stopTimer();
      return true;
    } catch (error) {
      this.handleError(error);
      return false;
    }
  }

  resumeRecording() {
    if (!this.isRecording || !this.isPaused) {
      return false;
    }

    try {
      this.mediaRecorder.resume();
      this.isPaused = false;
      this.startTimer();
      return true;
    } catch (error) {
      this.handleError(error);
      return false;
    }
  }

  stopRecording() {
    if (!this.isRecording) {
      return false;
    }

    try {
      this.mediaRecorder.stop();
      this.isRecording = false;
      this.isPaused = false;
      this.stopTimer();
      this.stopVisualization();
      return true;
    } catch (error) {
      this.handleError(error);
      return false;
    }
  }

  startTimer() {
    this.timerInterval = setInterval(() => {
      const elapsed = Date.now() - this.startTime;
      this.updateTimer(elapsed);
    }, 100);
  }

  stopTimer() {
    if (this.timerInterval) {
      clearInterval(this.timerInterval);
      this.timerInterval = null;
    }
  }

  updateTimer(elapsed) {
    const minutes = Math.floor(elapsed / 60000);
    const seconds = Math.floor((elapsed % 60000) / 1000);
    const timeString = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    
    const timerElement = document.querySelector('.timer');
    if (timerElement) {
      timerElement.textContent = timeString;
    }
  }

  startVisualization() {
    if (!this.analysisContext) return;

    const canvas = document.getElementById('visualizer');
    if (!canvas) return;

    const canvasContext = canvas.getContext('2d');
    const { analyser, dataArray } = this.analysisContext;

    const draw = () => {
      if (!this.isRecording || this.isPaused) return;

      analyser.getByteFrequencyData(dataArray);
      
      canvasContext.fillStyle = '#f9fafb';
      canvasContext.fillRect(0, 0, canvas.width, canvas.height);
      
      const barWidth = canvas.width / dataArray.length * 2;
      let x = 0;
      
      for (let i = 0; i < dataArray.length; i++) {
        const barHeight = (dataArray[i] / 255) * canvas.height * 0.8;
        
        canvasContext.fillStyle = `rgb(124, 58, 237)`;
        canvasContext.fillRect(x, canvas.height - barHeight, barWidth, barHeight);
        
        x += barWidth + 1;
      }
      
      requestAnimationFrame(draw);
    };
    
    draw();
  }

  stopVisualization() {
    const canvas = document.getElementById('visualizer');
    if (canvas) {
      const canvasContext = canvas.getContext('2d');
      canvasContext.clearRect(0, 0, canvas.width, canvas.height);
      canvasContext.fillStyle = '#f9fafb';
      canvasContext.fillRect(0, 0, canvas.width, canvas.height);
    }
  }

  async processRecording() {
    if (this.audioChunks.length === 0) {
      this.handleError(new Error('No audio data recorded'));
      return;
    }

    try {
      const audioBlob = new Blob(this.audioChunks, { 
        type: this.getSupportedMimeType() || 'audio/webm' 
      });
      
      await this.uploadRecording(audioBlob);
    } catch (error) {
      this.handleError(error);
    }
  }

  async uploadRecording(audioBlob) {
    const formData = new FormData();
    const filename = `recording_${Date.now()}.webm`;
    formData.append('file', audioBlob, filename);

    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      let progressIndicator = null;
      
      const cleanup = () => {
        if (progressIndicator) {
          progressIndicator.destroy();
          progressIndicator = null;
        }
      };

      try {
        this.updateStatus('Uploading recording...');
        
        const progressContainer = document.getElementById('progressContainer');
        if (progressContainer) {
          progressIndicator = new ProgressIndicator(progressContainer, {
            showSpeed: true,
            showETA: true,
            cancelable: true,
            onCancel: () => {
              xhr.abort();
            }
          });
          progressIndicator.show();
        } else {
          this.showProgress(true);
        }

        xhr.upload.addEventListener('progress', (event) => {
          if (event.lengthComputable && progressIndicator) {
            progressIndicator.update(event.loaded, event.total);
          }
        });

        xhr.addEventListener('load', () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            try {
              const result = JSON.parse(xhr.responseText);
              if (progressIndicator) {
                progressIndicator.complete();
              } else {
                this.showProgress(false);
              }
              this.handleUploadSuccess(result);
              resolve(result);
            } catch (parseError) {
              const error = new Error('Invalid response from server');
              this.handleUploadError(error, progressIndicator);
              reject(error);
            }
          } else {
            const error = new Error(`Upload failed: ${xhr.status} ${xhr.statusText}`);
            this.handleUploadError(error, progressIndicator);
            reject(error);
          }
        });

        xhr.addEventListener('error', () => {
          const error = new Error('Network error occurred during upload');
          this.handleUploadError(error, progressIndicator);
          reject(error);
        });

        xhr.addEventListener('abort', () => {
          const error = new Error('Upload was cancelled');
          this.handleUploadError(error, progressIndicator);
          reject(error);
        });

        xhr.addEventListener('timeout', () => {
          const error = new Error('Upload timed out');
          this.handleUploadError(error, progressIndicator);
          reject(error);
        });

        xhr.open('POST', '/api/v1/audio/upload');
        xhr.timeout = 300000; // 5 minute timeout
        xhr.send(formData);

      } catch (error) {
        this.handleUploadError(error, progressIndicator);
        reject(error);
      }
    });
  }

  handleUploadError(error, progressIndicator) {
    if (progressIndicator) {
      progressIndicator.setError(error.message);
      setTimeout(() => {
        progressIndicator.destroy();
      }, 5000);
    } else {
      this.showProgress(false);
    }
    this.handleError(error);
  }

  handleUploadSuccess(result) {
    this.updateStatus('Recording uploaded successfully!');
    console.log('Upload result:', result);
    
    setTimeout(() => {
      this.reset();
    }, 2000);
  }

  reset() {
    this.audioChunks = [];
    this.startTime = null;
    this.isRecording = false;
    this.isPaused = false;
    
    const timerElement = document.querySelector('.timer');
    if (timerElement) {
      timerElement.textContent = '00:00';
    }
    
    this.updateStatus('Tap the button to start recording');
    this.stopVisualization();
  }

  updateStatus(message) {
    const statusElement = document.getElementById('statusMessage');
    if (statusElement) {
      statusElement.textContent = message;
    }
  }

  showProgress(show) {
    const progressBar = document.getElementById('progressBar');
    if (progressBar) {
      progressBar.hidden = !show;
    }
  }

  handleError(error) {
    console.error('AudioRecorder error:', error);
    console.error('Error name:', error.name);
    console.error('Error message:', error.message);
    console.error('Error stack:', error.stack);
    
    let userMessage = 'An error occurred while recording.';
    
    if (error.name === 'NotAllowedError') {
      userMessage = 'Microphone access was denied. Please allow microphone access and try again.';
    } else if (error.name === 'NotFoundError') {
      userMessage = 'No microphone was found. Please connect a microphone and try again.';
    } else if (error.name === 'NotSupportedError') {
      userMessage = 'Audio recording is not supported in this browser.';
    } else if (error.name === 'SecurityError') {
      userMessage = 'Security error: Cannot access microphone. Please ensure you are using HTTPS.';
    } else if (error.name === 'AbortError') {
      userMessage = 'Microphone access was aborted.';
    } else if (error.message) {
      userMessage = error.message;
    }
    
    // Also log browser and environment info
    console.error('Browser info:', navigator.userAgent);
    console.error('HTTPS:', location.protocol === 'https:');
    console.error('MediaDevices available:', !!navigator.mediaDevices);
    console.error('getUserMedia available:', !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia));
    console.error('MediaRecorder available:', !!window.MediaRecorder);
    
    this.showError(userMessage);
    this.reset();
  }

  showError(message) {
    console.error('Recording error:', message);
    
    const errorModal = document.getElementById('errorModal');
    const errorMessage = document.getElementById('error-message');
    
    if (errorModal && errorMessage) {
      errorMessage.textContent = message;
      errorModal.hidden = false;
    }
  }

  destroy() {
    this.stopRecording();
    
    if (this.stream) {
      this.stream.getTracks().forEach(track => track.stop());
      this.stream = null;
    }
    
    if (this.analysisContext && this.analysisContext.audioContext) {
      this.analysisContext.audioContext.close();
    }
  }
}