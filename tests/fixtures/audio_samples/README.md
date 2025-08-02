# Test Audio Samples

This directory contains audio samples for integration testing. These files are stored using Git LFS due to their size.

## Sample Files

### short_sample.webm
- **Duration**: 30 seconds
- **Format**: WebM
- **Content**: "This is a short test recording for the voice notes system. It demonstrates basic transcription functionality."
- **Use**: Quick integration tests, API response time validation

### medium_sample.m4a
- **Duration**: 2 minutes
- **Format**: M4A
- **Content**: "This is a medium-length test recording that includes multiple sentences and paragraphs. It tests the system's ability to handle longer content with proper punctuation and structure."
- **Use**: Audio format conversion testing, medium-length processing

### long_sample.mp3
- **Duration**: 5 minutes
- **Format**: MP3
- **Content**: "This is a comprehensive five-minute test recording that validates the system meets performance requirements. It includes multiple topics, complex sentence structures, and various speaking patterns to thoroughly test transcription accuracy."
- **Use**: Performance benchmarks, meeting <35s processing requirement

### poor_quality.webm
- **Duration**: 45 seconds
- **Format**: WebM (low bitrate)
- **Content**: "This recording has intentionally poor audio quality to test the system's robustness and error handling capabilities."
- **Use**: Error handling tests, quality degradation scenarios

## Expected Outputs

The `expected_outputs/` directory contains the expected transcriptions and summaries for each sample file, used for accuracy validation.

## Usage in Tests

These samples are referenced in the test fixtures and used throughout the integration test suite. They provide consistent, reproducible test data for validating:

- Audio format support
- Transcription accuracy
- Processing performance
- Error handling
- End-to-end workflows

## Generating New Samples

To add new test samples:

1. Record or generate audio in the required format
2. Add to this directory
3. Create corresponding expected output in `expected_outputs/`
4. Update test fixtures to reference the new sample
5. Commit with Git LFS