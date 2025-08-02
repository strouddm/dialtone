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
    if (!this.checkBrowserSupport()) {
      throw new Error('Audio recording is not supported in this browser');
    }

    try {
      this.stream = await this.requestMicrophone();
      this.setupRecorder();
      this.setupAudioVisualization();
      return true;
    } catch (error) {
      this.handleError(error);
      throw error;
    }
  }

  checkBrowserSupport() {
    return !!(navigator.mediaDevices && 
              navigator.mediaDevices.getUserMedia && 
              window.MediaRecorder);
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

    return await navigator.mediaDevices.getUserMedia(constraints);
  }

  setupRecorder() {
    const mimeType = this.getSupportedMimeType();
    const options = mimeType ? { mimeType } : {};
    
    this.mediaRecorder = new MediaRecorder(this.stream, options);
    
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

    try {
      this.updateStatus('Uploading recording...');
      this.showProgress(true);

      const response = await fetch('/api/v1/audio/upload', {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        throw new Error(`Upload failed: ${response.status} ${response.statusText}`);
      }

      const result = await response.json();
      this.handleUploadSuccess(result);
    } catch (error) {
      this.handleError(error);
    } finally {
      this.showProgress(false);
    }
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
    
    let userMessage = 'An error occurred while recording.';
    
    if (error.name === 'NotAllowedError') {
      userMessage = 'Microphone access was denied. Please allow microphone access and try again.';
    } else if (error.name === 'NotFoundError') {
      userMessage = 'No microphone was found. Please connect a microphone and try again.';
    } else if (error.name === 'NotSupportedError') {
      userMessage = 'Audio recording is not supported in this browser.';
    } else if (error.message) {
      userMessage = error.message;
    }
    
    this.showError(userMessage);
    this.reset();
  }

  showError(message) {
    const errorModal = document.getElementById('errorModal');
    const errorMessage = document.getElementById('error-message');
    
    if (errorModal && errorMessage) {
      errorMessage.textContent = message;
      errorModal.hidden = false;
      errorModal.focus();
    } else {
      alert(message);
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