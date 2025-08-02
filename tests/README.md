# Integration Test Suite

Comprehensive integration test suite for the Dialtone voice-to-Obsidian system, validating end-to-end workflows, performance requirements, and system reliability.

## Overview

This test suite implements the integration testing plan from Issue #14, providing:

- **End-to-end workflow validation**
- **Audio processing pipeline tests**
- **AI services integration tests**
- **Performance benchmarks**
- **Load testing scenarios**
- **Docker environment testing**

## Test Structure

```
tests/
├── conftest.py                 # Common fixtures and configuration
├── integration/                # Integration test modules
│   ├── test_voice_workflow.py      # Complete workflow tests
│   ├── test_audio_processing.py    # Audio pipeline tests
│   ├── test_ai_integration.py      # AI services tests
│   └── test_vault_integration.py   # Obsidian integration tests
├── performance/                # Performance and load tests
│   ├── test_benchmarks.py          # Performance benchmarks
│   └── test_load_testing.py        # Load and stress tests
├── fixtures/                   # Test data and samples
│   ├── audio_samples/              # Test audio files (Git LFS)
│   └── expected_outputs/           # Expected test results
└── docker/                     # Docker test configurations
    └── test-environment.yml        # Test environment setup
```

## Test Categories

### Integration Tests (`-m integration`)
- **Voice Workflow**: End-to-end voice processing pipeline
- **Audio Processing**: Format conversion and handling
- **AI Integration**: Whisper transcription and Ollama summarization
- **Vault Integration**: Obsidian markdown generation and saving

### Performance Tests (`-m benchmark`)
- **5-minute Audio Processing**: Must complete in <35s (PRD requirement)
- **Concurrent Processing**: 3 simultaneous workflows
- **Memory Usage**: Must stay under 16GB (PRD requirement)
- **API Response Times**: Must respond in <500ms (PRD requirement)

### Load Tests (`-m load`)
- **High Volume Uploads**: 50 concurrent file uploads
- **Sustained Processing**: Extended operation under load
- **Session Management**: Concurrent session operations
- **Error Recovery**: System resilience under failure conditions

## Running Tests

### Local Development

```bash
# Run all tests
./scripts/run-tests.sh

# Run specific test categories
./scripts/run-tests.sh -t unit              # Fast unit tests
./scripts/run-tests.sh -t integration       # Integration tests
./scripts/run-tests.sh -t performance       # Performance tests
./scripts/run-tests.sh -t benchmark         # Benchmarks only

# With coverage and verbose output
./scripts/run-tests.sh -t integration -c -v

# Run in parallel (requires pytest-xdist)
./scripts/run-tests.sh -t unit -p
```

### Direct pytest Usage

```bash
# Fast development tests (exclude slow tests)
pytest tests/ -m "not slow and not benchmark" --maxfail=5

# Integration tests only
pytest tests/integration/ -m integration -v

# Performance benchmarks
pytest tests/performance/test_benchmarks.py -m benchmark --benchmark-only

# Load tests (may take 5-15 minutes)
pytest tests/performance/test_load_testing.py -m load

# Specific test with detailed output
pytest tests/integration/test_voice_workflow.py::TestVoiceProcessingWorkflow::test_complete_voice_note_processing -v -s
```

### Docker Testing

```bash
# Run tests in Docker environment
cd tests/docker
docker-compose -f test-environment.yml up -d
docker-compose -f test-environment.yml exec voice-notes-api-test pytest tests/integration/
docker-compose -f test-environment.yml down
```

## Performance Requirements Validation

The test suite validates all PRD performance requirements:

| Requirement | Test | Target |
|-------------|------|--------|
| 5-min audio processing | `test_5_minute_audio_processing_time` | <35 seconds |
| API response time | `test_api_response_times` | <500ms |
| Memory usage | `test_memory_usage_under_load` | <16GB |
| Concurrent processing | `test_concurrent_processing_performance` | 3 simultaneous |
| Transcription accuracy | `test_whisper_transcription_accuracy` | >95% |

## Test Data and Fixtures

### Audio Samples (Git LFS)
- **short_sample.webm**: 30s test recording for quick validation
- **medium_sample.m4a**: 2min recording for format testing
- **long_sample.mp3**: 5min recording for performance validation
- **poor_quality.webm**: Low-quality audio for error handling

### Expected Outputs
JSON files containing expected transcriptions, summaries, and keywords for accuracy validation.

### Test Fixtures
- `async_client`: Async HTTP client for API testing
- `test_obsidian_vault`: Temporary vault for testing
- `mock_whisper_service`: Mocked Whisper service
- `mock_ollama_service`: Mocked Ollama service
- `test_audio_content`: Binary audio data for testing

## Continuous Integration

### GitHub Actions Workflows

#### Integration Tests (`.github/workflows/integration-tests.yml`)
- **Triggers**: Push to main/develop, pull requests
- **Jobs**: Unit tests, integration tests, performance tests, Docker tests
- **Matrix Strategy**: Parallel execution across test groups
- **Artifacts**: Coverage reports, benchmark results

#### Performance Monitoring (`.github/workflows/performance-monitoring.yml`)
- **Schedule**: Daily at 2 AM UTC
- **Purpose**: Detect performance regressions
- **Alerts**: Creates GitHub issues for performance degradation
- **Tracking**: Archives daily performance metrics

### Test Execution Strategy

1. **Fast Tests** (< 30s): Unit and service tests run first
2. **Integration Tests** (2-5 min): Core workflow validation
3. **Performance Tests** (5-15 min): Benchmark and load testing
4. **Docker Tests** (5-10 min): Full containerized environment

## Configuration

### pytest.ini
- Test discovery patterns
- Marker definitions
- Async test support
- Coverage configuration
- Logging setup

### Environment Variables
```bash
TESTING=true                    # Enable test mode
OBSIDIAN_VAULT_PATH=/tmp/vault  # Test vault location
UPLOAD_DIR=/tmp/uploads         # Test upload directory
SESSION_STORAGE_DIR=/tmp/sessions # Test session storage
LOG_LEVEL=DEBUG                 # Detailed logging
```

## Best Practices

### Test Development
1. **Isolation**: Each test is independent and can run in any order
2. **Cleanup**: Tests clean up after themselves (temp files, mock state)
3. **Mocking**: External dependencies (AI services) are mocked for reliability
4. **Data**: Use fixtures and factories for consistent test data
5. **Assertions**: Clear, specific assertions with helpful error messages

### Performance Testing
1. **Baseline**: Establish performance baselines for comparison
2. **Consistency**: Run tests in consistent environments
3. **Monitoring**: Track performance metrics over time
4. **Regression**: Alert on performance degradation
5. **Realistic**: Use realistic data sizes and scenarios

### Integration Testing
1. **Real Dependencies**: Test with actual service integrations where possible
2. **Error Scenarios**: Test failure modes and recovery
3. **Edge Cases**: Test boundary conditions and limits
4. **Concurrency**: Validate thread-safety and concurrent operations
5. **End-to-End**: Test complete user workflows

## Troubleshooting

### Common Issues

#### Tests Hanging
- Check for async/await issues in test code
- Verify mock services are responding correctly
- Ensure proper cleanup of resources

#### Performance Test Failures
- Check system resources (CPU, memory)
- Verify no other processes are interfering
- Review performance baseline expectations

#### Integration Test Failures
- Verify test environment setup (directories, permissions)
- Check Docker service health
- Review log output for service errors

#### Flaky Tests
- Add retry logic for network-dependent tests
- Increase timeouts for slow operations
- Improve test isolation and cleanup

### Debugging

```bash
# Run with detailed output
pytest tests/integration/test_voice_workflow.py -v -s --tb=long

# Run specific test with debugging
pytest tests/integration/test_voice_workflow.py::TestVoiceProcessingWorkflow::test_complete_voice_note_processing -v -s --pdb

# Generate coverage report
pytest tests/ --cov=app --cov-report=html
open htmlcov/index.html

# Run with profiling
pytest tests/performance/ --profile --profile-svg
```

## Contributing

### Adding New Tests
1. Follow existing test patterns and naming conventions
2. Add appropriate markers (`@pytest.mark.integration`, etc.)
3. Include docstrings explaining test purpose
4. Update test documentation if adding new categories

### Performance Baselines
1. Run tests locally to establish baseline
2. Document expected performance ranges
3. Update CI thresholds if requirements change
4. Monitor for regressions in daily runs

### Test Data
1. Use Git LFS for binary test files
2. Keep test data minimal but representative
3. Document expected outputs
4. Version test data with code changes

## Metrics and Reporting

The test suite provides comprehensive metrics:

- **Coverage**: Line and branch coverage reports
- **Performance**: Benchmark timing and memory usage
- **Quality**: Code quality and security scans
- **Reliability**: Test success rates and flake detection
- **Trends**: Historical performance tracking

Results are available in:
- GitHub Actions job summaries
- Uploaded artifacts (coverage, benchmarks)
- Performance tracking files
- Security scan reports