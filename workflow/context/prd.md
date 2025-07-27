# Product Requirements Document

## Overview
Self-hosted voice-to-Obsidian system. Record on phone → AI transcribe/summarize → Review → Save to vault.

## Users
- Primary: Obsidian users who want voice notes
- Tech level: Can run Docker

## Core Features
1. Mobile web recording (PWA)
2. Local AI transcription (Whisper)
3. AI summarization (Ollama)
4. Edit before saving
5. Direct Obsidian vault integration
6. Offline queue with sync

## Success Metrics
- Process 5-min audio in <35s
- 95%+ transcription accuracy
- <3 taps to save note
- <16GB RAM usage

## Constraints
- Hardware: 6 cores, 16GB RAM
- All processing local (privacy)
- Docker deployment
- HTTPS required for mobile

## Key Requirements

### Functional
- Audio formats: WebM, M4A, MP3 (50MB max)
- Auto-convert to 16kHz mono
- Bullet-point summaries
- Extract 3-5 keywords
- Markdown with YAML frontmatter
- Session recovery

### Non-Functional
- API response <500ms
- 3 concurrent recordings
- Automatic cleanup
- Health endpoints
- Graceful fallbacks

## Sprint Plan

### Sprint 1: Foundation (Week 1-2)
**Goal**: Basic API that accepts audio and returns transcription

Issues:
- `#1` Setup Docker environment with Python/FastAPI
- `#2` Implement audio upload endpoint
- `#3` Integrate Whisper for transcription
- `#4` Add basic error handling
- `#5` Create health check endpoint
- `#6` Setup GitHub Actions CI
- `#7` Write API documentation

### Sprint 2: AI Processing (Week 3-4)
**Goal**: Add summarization and Obsidian integration

Issues:
- `#8` Setup Ollama container
- `#9` Implement summarization service
- `#10` Add keyword extraction
- `#11` Create Obsidian markdown formatter
- `#12` Implement file saving to vault
- `#13` Add session management
- `#14` Create integration tests

### Sprint 3: Web Interface (Week 5-6)
**Goal**: Mobile-friendly recording interface

Issues:
- `#15` Create HTML/CSS recording interface
- `#16` Implement audio recording with MediaRecorder
- `#17` Add upload progress indicator
- `#18` Create review/edit screen
- `#19` Implement PWA manifest
- `#20` Add service worker for offline
- `#21` Setup HTTPS with Nginx

### Sprint 4: Polish & Deploy (Week 7-8)
**Goal**: Production-ready with documentation

Issues:
- `#22` Add request queuing system
- `#23` Implement rate limiting
- `#24` Create setup script
- `#25` Write user documentation
- `#26` Add monitoring/metrics
- `#27` Performance optimization
- `#28` Security audit checklist