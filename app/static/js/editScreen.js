/**
 * Edit Screen Module - Mobile-friendly review and edit interface
 * Handles transcription editing, summary modification, and keyword management
 */

class EditScreen {
    constructor(sessionId, sessionData) {
        this.sessionId = sessionId;
        this.originalData = {
            transcription: sessionData.transcription?.text || '',
            summary: sessionData.summary ? sessionData.summary.split('\n').filter(s => s.trim()) : [],
            keywords: sessionData.keywords || []
        };
        
        // Current editing state
        this.currentData = {
            transcription: this.originalData.transcription,
            summary: [...this.originalData.summary],
            keywords: [...this.originalData.keywords]
        };
        
        // Auto-save and undo management
        this.autoSaveTimer = null;
        this.autoSaveDelay = 10000; // 10 seconds
        this.undoStack = [];
        this.redoStack = [];
        this.maxUndoSteps = 10;
        
        // UI elements
        this.container = null;
        this.transcriptionEditor = null;
        this.summaryContainer = null;
        this.keywordsContainer = null;
        this.previewContainer = null;
        
        // Flags
        this.hasUnsavedChanges = false;
        this.isAutoSaving = false;
        
        this.init();
    }
    
    async init() {
        await this.render();
        this.setupEventListeners();
        this.setupAutoSave();
        this.loadFromLocalStorage();
        
        // Add to undo stack for initial state
        this.saveToUndoStack();
    }
    
    async render() {
        // Create main edit container
        this.container = document.createElement('div');
        this.container.className = 'edit-screen';
        this.container.innerHTML = `
            <div class="edit-header">
                <button class="back-button" id="backButton" type="button" aria-label="Go back">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                        <path d="M19 12H5m7-7l-7 7 7 7" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                </button>
                <h2 class="edit-title">Edit Your Note</h2>
                <div class="edit-actions">
                    <button class="action-button undo-button" id="undoButton" type="button" disabled aria-label="Undo">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                            <path d="M3 7v6h6m2-2a9 9 0 1 1-2.6-4.6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                        </svg>
                    </button>
                    <button class="action-button redo-button" id="redoButton" type="button" disabled aria-label="Redo">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                            <path d="M21 7v6h-6m-2-2a9 9 0 1 0 2.6-4.6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                        </svg>
                    </button>
                </div>
            </div>
            
            <div class="edit-content">
                <div class="edit-tabs">
                    <button class="tab-button active" data-tab="transcription">Transcription</button>
                    <button class="tab-button" data-tab="summary">Summary</button>
                    <button class="tab-button" data-tab="keywords">Keywords</button>
                    <button class="tab-button" data-tab="preview">Preview</button>
                </div>
                
                <div class="tab-content">
                    <div class="tab-panel active" id="transcriptionTab">
                        <div class="editor-header">
                            <label for="transcriptionEditor" class="section-label">Edit Transcription</label>
                            <div class="character-count" id="transcriptionCount">0 characters</div>
                        </div>
                        <textarea 
                            id="transcriptionEditor" 
                            class="transcription-editor"
                            placeholder="Your transcription will appear here..."
                            rows="12"
                        ></textarea>
                    </div>
                    
                    <div class="tab-panel" id="summaryTab">
                        <div class="editor-header">
                            <label class="section-label">Edit Summary Points</label>
                            <button class="add-button" id="addSummaryPoint" type="button">+ Add Point</button>
                        </div>
                        <div class="summary-list" id="summaryList"></div>
                    </div>
                    
                    <div class="tab-panel" id="keywordsTab">
                        <div class="editor-header">
                            <label class="section-label">Keywords</label>
                            <div class="keyword-input-container">
                                <input type="text" id="keywordInput" class="keyword-input" placeholder="Add keyword..." maxlength="50">
                                <button class="add-button" id="addKeyword" type="button">Add</button>
                            </div>
                        </div>
                        <div class="keywords-container" id="keywordsList"></div>
                    </div>
                    
                    <div class="tab-panel" id="previewTab">
                        <div class="editor-header">
                            <label class="section-label">Markdown Preview</label>
                            <div class="preview-stats" id="previewStats"></div>
                        </div>
                        <div class="preview-content" id="previewContent">
                            <div class="loading-spinner">Generating preview...</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="edit-footer">
                <div class="save-status" id="saveStatus">
                    <span class="status-icon"></span>
                    <span class="status-text">Ready to save</span>
                </div>
                <div class="action-buttons">
                    <button class="discard-button" id="discardButton" type="button">Discard</button>
                    <button class="save-button" id="saveButton" type="button">Save to Vault</button>
                </div>
            </div>
        `;
        
        // Replace the main content
        const mainContainer = document.querySelector('.recorder-container');
        mainContainer.style.display = 'none';
        document.body.appendChild(this.container);
        
        // Get references to UI elements
        this.transcriptionEditor = this.container.querySelector('#transcriptionEditor');
        this.summaryContainer = this.container.querySelector('#summaryList');
        this.keywordsContainer = this.container.querySelector('#keywordsList');
        this.previewContainer = this.container.querySelector('#previewContent');
        
        // Populate initial data
        this.populateData();
    }
    
    populateData() {
        // Set transcription text
        this.transcriptionEditor.value = this.currentData.transcription;
        this.updateCharacterCount();
        
        // Render summary points
        this.renderSummaryPoints();
        
        // Render keywords
        this.renderKeywords();
    }
    
    renderSummaryPoints() {
        this.summaryContainer.innerHTML = '';
        
        this.currentData.summary.forEach((point, index) => {
            const pointElement = document.createElement('div');
            pointElement.className = 'summary-point';
            pointElement.innerHTML = `
                <div class="point-content">
                    <span class="point-bullet">•</span>
                    <textarea 
                        class="point-editor" 
                        rows="2" 
                        data-index="${index}"
                        placeholder="Enter summary point..."
                    >${point}</textarea>
                </div>
                <button class="remove-point" data-index="${index}" type="button" aria-label="Remove point">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                        <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                </button>
            `;
            this.summaryContainer.appendChild(pointElement);
        });
        
        // Add empty point if no summary points exist
        if (this.currentData.summary.length === 0) {
            this.addSummaryPoint();
        }
    }
    
    renderKeywords() {
        this.keywordsContainer.innerHTML = '';
        
        this.currentData.keywords.forEach((keyword, index) => {
            const keywordElement = document.createElement('div');
            keywordElement.className = 'keyword-tag';
            
            // Create elements safely to prevent XSS
            const textSpan = document.createElement('span');
            textSpan.className = 'keyword-text';
            textSpan.textContent = keyword; // Use textContent to prevent XSS
            
            const removeButton = document.createElement('button');
            removeButton.className = 'remove-keyword';
            removeButton.setAttribute('data-index', index);
            removeButton.setAttribute('type', 'button');
            removeButton.setAttribute('aria-label', 'Remove keyword');
            removeButton.innerHTML = `
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                    <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
            `;
            
            keywordElement.appendChild(textSpan);
            keywordElement.appendChild(removeButton);
            this.keywordsContainer.appendChild(keywordElement);
        });
    }
    
    setupEventListeners() {
        // Tab navigation
        this.container.querySelectorAll('.tab-button').forEach(button => {
            button.addEventListener('click', (e) => this.switchTab(e.target.dataset.tab));
        });
        
        // Transcription editing
        this.transcriptionEditor.addEventListener('input', () => {
            this.onTranscriptionChange();
        });
        
        // Summary editing
        this.container.addEventListener('click', (e) => {
            if (e.target.id === 'addSummaryPoint') {
                this.addSummaryPoint();
            } else if (e.target.closest('.remove-point')) {
                const index = parseInt(e.target.closest('.remove-point').dataset.index);
                this.removeSummaryPoint(index);
            }
        });
        
        this.container.addEventListener('input', (e) => {
            if (e.target.classList.contains('point-editor')) {
                const index = parseInt(e.target.dataset.index);
                this.updateSummaryPoint(index, e.target.value);
            }
        });
        
        // Keywords
        const keywordInput = this.container.querySelector('#keywordInput');
        const addKeywordBtn = this.container.querySelector('#addKeyword');
        
        addKeywordBtn.addEventListener('click', () => this.addKeyword());
        keywordInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.addKeyword();
            }
        });
        
        this.container.addEventListener('click', (e) => {
            if (e.target.closest('.remove-keyword')) {
                const index = parseInt(e.target.closest('.remove-keyword').dataset.index);
                this.removeKeyword(index);
            }
        });
        
        // Action buttons
        this.container.querySelector('#undoButton').addEventListener('click', () => this.undo());
        this.container.querySelector('#redoButton').addEventListener('click', () => this.redo());
        this.container.querySelector('#backButton').addEventListener('click', () => this.goBack());
        this.container.querySelector('#discardButton').addEventListener('click', () => this.confirmDiscard());
        this.container.querySelector('#saveButton').addEventListener('click', () => this.saveToVault());
        
        // Prevent accidental navigation
        window.addEventListener('beforeunload', (e) => {
            if (this.hasUnsavedChanges) {
                e.preventDefault();
                e.returnValue = '';
            }
        });
    }
    
    switchTab(tabName) {
        // Update active tab button
        this.container.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
        this.container.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
        
        // Update active tab panel
        this.container.querySelectorAll('.tab-panel').forEach(panel => panel.classList.remove('active'));
        this.container.querySelector(`#${tabName}Tab`).classList.add('active');
        
        // Load preview if switching to preview tab
        if (tabName === 'preview') {
            this.updatePreview();
        }
    }
    
    onTranscriptionChange() {
        this.currentData.transcription = this.transcriptionEditor.value;
        this.updateCharacterCount();
        this.markAsChanged();
        this.scheduleAutoSave();
    }
    
    updateCharacterCount() {
        const count = this.transcriptionEditor.value.length;
        const countElement = this.container.querySelector('#transcriptionCount');
        countElement.textContent = `${count} characters`;
    }
    
    addSummaryPoint() {
        this.saveToUndoStack();
        this.currentData.summary.push('');
        this.renderSummaryPoints();
        this.markAsChanged();
        
        // Focus the new point editor
        const newEditor = this.container.querySelector('.point-editor:last-child');
        if (newEditor) newEditor.focus();
    }
    
    removeSummaryPoint(index) {
        if (this.currentData.summary.length <= 1) return; // Keep at least one point
        
        this.saveToUndoStack();
        this.currentData.summary.splice(index, 1);
        this.renderSummaryPoints();
        this.markAsChanged();
        this.scheduleAutoSave();
    }
    
    updateSummaryPoint(index, value) {
        this.currentData.summary[index] = value;
        this.markAsChanged();
        this.scheduleAutoSave();
    }
    
    addKeyword() {
        const input = this.container.querySelector('#keywordInput');
        const keyword = input.value.trim();
        
        if (keyword && !this.currentData.keywords.includes(keyword)) {
            this.saveToUndoStack();
            this.currentData.keywords.push(keyword);
            this.renderKeywords();
            this.markAsChanged();
            this.scheduleAutoSave();
            input.value = '';
        }
    }
    
    removeKeyword(index) {
        this.saveToUndoStack();
        this.currentData.keywords.splice(index, 1);
        this.renderKeywords();
        this.markAsChanged();
        this.scheduleAutoSave();
    }
    
    async updatePreview() {
        const previewElement = this.container.querySelector('#previewContent');
        const statsElement = this.container.querySelector('#previewStats');
        
        previewElement.innerHTML = '<div class="loading-spinner">Generating preview...</div>';
        
        try {
            const response = await fetch(`/api/v1/sessions/${this.sessionId}/preview`);
            if (!response.ok) throw new Error('Failed to generate preview');
            
            const data = await response.json();
            
            // Safely display markdown content to prevent XSS
            const preEl = document.createElement('pre');
            preEl.className = 'markdown-preview';
            preEl.textContent = data.markdown; // Use textContent to prevent XSS
            previewElement.innerHTML = '';
            previewElement.appendChild(preEl);
            
            statsElement.innerHTML = `
                <span>${data.character_count} characters</span>
                <span>${data.word_count} words</span>
            `;
        } catch (error) {
            const errorDiv = document.createElement('div');
            errorDiv.className = 'preview-error';
            errorDiv.textContent = `Failed to generate preview: ${error.message}`; // Safe error display
            previewElement.innerHTML = '';
            previewElement.appendChild(errorDiv);
            statsElement.innerHTML = '';
        }
    }
    
    saveToUndoStack() {
        const state = {
            transcription: this.currentData.transcription,
            summary: [...this.currentData.summary],
            keywords: [...this.currentData.keywords]
        };
        
        this.undoStack.push(state);
        if (this.undoStack.length > this.maxUndoSteps) {
            this.undoStack.shift();
        }
        
        // Clear redo stack when new action is performed
        this.redoStack = [];
        this.updateUndoRedoButtons();
    }
    
    undo() {
        if (this.undoStack.length === 0) return;
        
        // Save current state to redo stack
        const currentState = {
            transcription: this.currentData.transcription,
            summary: [...this.currentData.summary],
            keywords: [...this.currentData.keywords]
        };
        this.redoStack.push(currentState);
        
        // Restore previous state
        const previousState = this.undoStack.pop();
        this.currentData = previousState;
        this.populateData();
        this.markAsChanged();
        this.updateUndoRedoButtons();
    }
    
    redo() {
        if (this.redoStack.length === 0) return;
        
        // Save current state to undo stack
        this.saveToUndoStack();
        
        // Restore next state
        const nextState = this.redoStack.pop();
        this.currentData = nextState;
        this.populateData();
        this.markAsChanged();
        this.updateUndoRedoButtons();
    }
    
    updateUndoRedoButtons() {
        const undoBtn = this.container.querySelector('#undoButton');
        const redoBtn = this.container.querySelector('#redoButton');
        
        undoBtn.disabled = this.undoStack.length === 0;
        redoBtn.disabled = this.redoStack.length === 0;
    }
    
    markAsChanged() {
        this.hasUnsavedChanges = true;
        this.updateSaveStatus('Modified');
    }
    
    scheduleAutoSave() {
        if (this.autoSaveTimer) {
            clearTimeout(this.autoSaveTimer);
        }
        
        this.autoSaveTimer = setTimeout(() => {
            this.autoSave();
        }, this.autoSaveDelay);
    }
    
    async autoSave() {
        if (this.isAutoSaving) return;
        
        this.isAutoSaving = true;
        this.updateSaveStatus('Auto-saving...');
        
        try {
            const draftData = {
                transcription: this.currentData.transcription,
                summary: this.currentData.summary.filter(s => s.trim()),
                keywords: this.currentData.keywords
            };
            
            const response = await fetch(`/api/v1/sessions/${this.sessionId}/draft`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(draftData)
            });
            
            if (!response.ok) throw new Error('Auto-save failed');
            
            // Save to localStorage as backup
            this.saveToLocalStorage();
            
            this.updateSaveStatus('Auto-saved');
            setTimeout(() => this.updateSaveStatus('Ready to save'), 2000);
            
        } catch (error) {
            console.error('Auto-save failed:', error);
            this.updateSaveStatus('Auto-save failed');
            setTimeout(() => this.updateSaveStatus('Modified'), 2000);
        } finally {
            this.isAutoSaving = false;
        }
    }
    
    setupAutoSave() {
        // Initial auto-save setup
        this.scheduleAutoSave();
    }
    
    saveToLocalStorage() {
        const storageKey = `dialtone_draft_${this.sessionId}`;
        const draftData = {
            transcription: this.currentData.transcription,
            summary: this.currentData.summary,
            keywords: this.currentData.keywords,
            timestamp: Date.now()
        };
        
        try {
            localStorage.setItem(storageKey, JSON.stringify(draftData));
        } catch (error) {
            console.warn('Failed to save to localStorage:', error);
        }
    }
    
    loadFromLocalStorage() {
        const storageKey = `dialtone_draft_${this.sessionId}`;
        
        try {
            const stored = localStorage.getItem(storageKey);
            if (stored) {
                const draftData = JSON.parse(stored);
                
                // Check if draft is recent (within 24 hours)
                const maxAge = 24 * 60 * 60 * 1000; // 24 hours
                if (Date.now() - draftData.timestamp < maxAge) {
                    this.currentData = {
                        transcription: draftData.transcription || this.currentData.transcription,
                        summary: draftData.summary || this.currentData.summary,
                        keywords: draftData.keywords || this.currentData.keywords
                    };
                    this.populateData();
                    this.markAsChanged();
                }
            }
        } catch (error) {
            console.warn('Failed to load from localStorage:', error);
        }
    }
    
    clearLocalStorage() {
        const storageKey = `dialtone_draft_${this.sessionId}`;
        try {
            localStorage.removeItem(storageKey);
        } catch (error) {
            console.warn('Failed to clear localStorage:', error);
        }
    }
    
    updateSaveStatus(status) {
        const statusText = this.container.querySelector('.status-text');
        const statusIcon = this.container.querySelector('.status-icon');
        
        statusText.textContent = status;
        
        // Update icon based on status
        statusIcon.className = 'status-icon';
        if (status.includes('saving') || status.includes('Saving')) {
            statusIcon.classList.add('loading');
        } else if (status.includes('saved') || status.includes('Saved')) {
            statusIcon.classList.add('success');
        } else if (status.includes('failed') || status.includes('Failed')) {
            statusIcon.classList.add('error');
        }
    }
    
    confirmDiscard() {
        if (this.hasUnsavedChanges) {
            const confirmed = confirm('Are you sure you want to discard your changes? This cannot be undone.');
            if (!confirmed) return;
        }
        
        this.clearLocalStorage();
        this.goBack();
    }
    
    goBack() {
        // Clear auto-save timer
        if (this.autoSaveTimer) {
            clearTimeout(this.autoSaveTimer);
        }
        
        // Remove edit screen
        this.container.remove();
        
        // Show main recorder interface
        const mainContainer = document.querySelector('.recorder-container');
        mainContainer.style.display = 'block';
        
        // Reset recorder state if needed
        if (window.audioRecorder && window.audioRecorder.resetUI) {
            window.audioRecorder.resetUI();
        }
    }
    
    async saveToVault() {
        const saveButton = this.container.querySelector('#saveButton');
        const originalText = saveButton.textContent;
        
        saveButton.disabled = true;
        saveButton.textContent = 'Saving...';
        this.updateSaveStatus('Saving to vault...');
        
        try {
            // First, save the current draft
            const draftData = {
                transcription: this.currentData.transcription,
                summary: this.currentData.summary.filter(s => s.trim()),
                keywords: this.currentData.keywords
            };
            
            await fetch(`/api/v1/sessions/${this.sessionId}/draft`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(draftData)
            });
            
            // Then save to vault (this would integrate with existing vault API)
            const vaultResponse = await fetch('/api/v1/vault/save', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: this.sessionId
                })
            });
            
            if (!vaultResponse.ok) {
                throw new Error('Failed to save to vault');
            }
            
            // Success
            this.hasUnsavedChanges = false;
            this.clearLocalStorage();
            this.updateSaveStatus('Saved successfully!');
            
            // Show success message and navigate back
            setTimeout(() => {
                alert('Note saved to your Obsidian vault successfully!');
                this.goBack();
            }, 1000);
            
        } catch (error) {
            console.error('Save failed:', error);
            this.updateSaveStatus('Save failed');
            alert(`Failed to save note: ${error.message}`);
        } finally {
            saveButton.disabled = false;
            saveButton.textContent = originalText;
        }
    }
}

// Export for use by other modules
window.EditScreen = EditScreen;