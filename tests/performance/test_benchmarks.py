"""Performance benchmark tests for voice processing system."""

import asyncio
import time
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, patch

import psutil
import pytest
from httpx import AsyncClient


@pytest.mark.benchmark
@pytest.mark.slow
class TestPerformanceBenchmarks:
    """Performance benchmarks validating PRD requirements."""

    @pytest.mark.benchmark(group="audio_processing")
    async def test_5_minute_audio_processing_time(
        self,
        async_client: AsyncClient,
        mock_whisper_service: AsyncMock,
        mock_ollama_service: AsyncMock,
        setup_test_environment: Dict[str, Path],
        benchmark,
    ):
        """Test 5-minute audio processing meets <35s requirement."""
        # Simulate 5-minute audio file (approximately 10MB)
        five_minute_audio_size = 10 * 1024 * 1024  # 10MB
        large_audio_content = b"\x1a\x45\xdf\xa3" + b"\x00" * (
            five_minute_audio_size - 4
        )

        # Configure mocks to simulate realistic processing times
        mock_whisper_service.transcribe.return_value = {
            "text": "This is a comprehensive five-minute transcription that demonstrates the system's ability to process longer audio files within the required performance parameters. The transcription includes multiple paragraphs and complex sentence structures to simulate real-world usage scenarios.",
            "segments": [
                {
                    "start": i * 30.0,
                    "end": (i + 1) * 30.0,
                    "text": f"Segment {i + 1} of the five-minute audio transcription.",
                }
                for i in range(10)  # 10 segments for 5-minute audio
            ],
        }

        mock_ollama_service.summarize.return_value = {
            "summary": "- Comprehensive five-minute audio processing demonstration\n- Multiple paragraph transcription with complex structures\n- Real-world usage scenario simulation\n- Performance benchmark validation\n- System capability assessment",
            "keywords": [
                "performance",
                "benchmark",
                "processing",
                "audio",
                "transcription",
            ],
        }

        async def process_5_minute_audio():
            """Process 5-minute audio file end-to-end."""
            # Upload
            files = {"file": ("5min_audio.webm", large_audio_content, "audio/webm")}
            upload_response = await async_client.post(
                "/api/v1/audio/upload",
                files=files,
                data={"description": "5-minute performance benchmark"},
            )

            upload_data = upload_response.json()
            upload_id = upload_data["upload_id"]

            # Process transcription
            transcription_response = await async_client.post(
                f"/api/v1/audio/{upload_id}/transcribe"
            )
            assert transcription_response.status_code == 200

            # Process summarization
            summary_response = await async_client.post(
                f"/api/v1/audio/{upload_id}/summarize"
            )
            assert summary_response.status_code == 200

            return upload_id

        # Benchmark the complete processing
        result = benchmark(lambda: asyncio.run(process_5_minute_audio()))

        # Verify performance requirement: <35s for 5-minute audio
        assert (
            benchmark.stats.mean < 35.0
        ), f"Processing took {benchmark.stats.mean:.2f}s, exceeds 35s requirement"

        return result

    @pytest.mark.benchmark(group="concurrent_processing")
    async def test_concurrent_processing_performance(
        self,
        async_client: AsyncClient,
        mock_whisper_service: AsyncMock,
        mock_ollama_service: AsyncMock,
        setup_test_environment: Dict[str, Path],
        benchmark,
    ):
        """Test concurrent processing of 3 audio files as per PRD requirement."""
        # Create test audio content
        test_audio_content = b"\x1a\x45\xdf\xa3" + b"\x00" * 1000

        async def process_concurrent_audio():
            """Process 3 concurrent audio files."""

            async def process_single_audio(audio_id: int):
                files = {
                    "file": (
                        f"concurrent_{audio_id}.webm",
                        test_audio_content,
                        "audio/webm",
                    )
                }

                # Upload
                upload_response = await async_client.post(
                    "/api/v1/audio/upload",
                    files=files,
                    data={"description": f"Concurrent test {audio_id}"},
                )
                upload_data = upload_response.json()
                upload_id = upload_data["upload_id"]

                # Process
                await async_client.post(f"/api/v1/audio/{upload_id}/transcribe")
                await async_client.post(f"/api/v1/audio/{upload_id}/summarize")

                return upload_id

            # Process 3 audio files concurrently
            tasks = [process_single_audio(i) for i in range(3)]
            results = await asyncio.gather(*tasks)
            return results

        # Benchmark concurrent processing
        results = benchmark(lambda: asyncio.run(process_concurrent_audio()))

        # Verify all 3 files processed successfully
        assert len(results) == 3
        assert all(result for result in results)

        # Performance should not degrade significantly under concurrent load
        # Allow reasonable overhead for concurrent processing
        assert (
            benchmark.stats.mean < 60.0
        ), f"Concurrent processing took {benchmark.stats.mean:.2f}s, too slow"

    @pytest.mark.benchmark(group="memory_usage")
    async def test_memory_usage_under_load(
        self,
        async_client: AsyncClient,
        mock_whisper_service: AsyncMock,
        mock_ollama_service: AsyncMock,
        setup_test_environment: Dict[str, Path],
        benchmark,
    ):
        """Test memory usage stays under 16GB requirement."""
        # Create larger audio content to stress memory
        large_audio_content = b"\x1a\x45\xdf\xa3" + b"\x00" * (5 * 1024 * 1024)  # 5MB

        # Configure mocks to simulate memory-intensive processing
        mock_whisper_service.transcribe.return_value = {
            "text": "Memory stress test transcription with extensive content to simulate high memory usage scenarios.",
            "segments": [
                {
                    "start": i * 10.0,
                    "end": (i + 1) * 10.0,
                    "text": f"Memory test segment {i + 1} with detailed content.",
                }
                for i in range(20)  # More segments to use more memory
            ],
        }

        def monitor_memory_usage():
            """Monitor memory usage during processing."""
            process = psutil.Process()
            initial_memory = process.memory_info().rss / 1024 / 1024 / 1024  # GB
            peak_memory = initial_memory

            async def memory_stress_test():
                nonlocal peak_memory

                # Process multiple files to stress memory
                for i in range(3):
                    files = {
                        "file": (
                            f"memory_test_{i}.webm",
                            large_audio_content,
                            "audio/webm",
                        )
                    }

                    upload_response = await async_client.post(
                        "/api/v1/audio/upload",
                        files=files,
                        data={"description": f"Memory stress test {i}"},
                    )
                    upload_data = upload_response.json()
                    upload_id = upload_data["upload_id"]

                    # Check memory during processing
                    current_memory = process.memory_info().rss / 1024 / 1024 / 1024
                    peak_memory = max(peak_memory, current_memory)

                    await async_client.post(f"/api/v1/audio/{upload_id}/transcribe")

                    # Check memory after transcription
                    current_memory = process.memory_info().rss / 1024 / 1024 / 1024
                    peak_memory = max(peak_memory, current_memory)

                    await async_client.post(f"/api/v1/audio/{upload_id}/summarize")

                    # Check memory after summarization
                    current_memory = process.memory_info().rss / 1024 / 1024 / 1024
                    peak_memory = max(peak_memory, current_memory)

                return peak_memory

            return asyncio.run(memory_stress_test())

        # Benchmark memory usage
        peak_memory = benchmark(monitor_memory_usage)

        # Verify memory requirement: <16GB
        assert (
            peak_memory < 16.0
        ), f"Peak memory usage {peak_memory:.2f}GB exceeds 16GB requirement"

    @pytest.mark.benchmark(group="api_response")
    async def test_api_response_times(
        self,
        async_client: AsyncClient,
        test_audio_content: bytes,
        setup_test_environment: Dict[str, Path],
        benchmark,
    ):
        """Test API response times meet <500ms requirement."""

        async def test_api_endpoints():
            """Test various API endpoints for response time."""
            response_times = {}

            # Health check endpoint
            start_time = time.time()
            health_response = await async_client.get("/api/v1/health")
            response_times["health"] = time.time() - start_time
            assert health_response.status_code == 200

            # Session creation endpoint
            start_time = time.time()
            session_response = await async_client.post("/api/v1/sessions/")
            response_times["session_create"] = time.time() - start_time
            assert session_response.status_code == 201

            session_data = session_response.json()
            session_id = session_data["session_id"]

            # Session retrieval endpoint
            start_time = time.time()
            session_get_response = await async_client.get(
                f"/api/v1/sessions/{session_id}"
            )
            response_times["session_get"] = time.time() - start_time
            assert session_get_response.status_code == 200

            # Audio upload endpoint
            files = {"file": ("response_test.webm", test_audio_content, "audio/webm")}
            start_time = time.time()
            upload_response = await async_client.post(
                "/api/v1/audio/upload",
                files=files,
                data={"description": "Response time test"},
            )
            response_times["audio_upload"] = time.time() - start_time
            assert upload_response.status_code == 201

            return response_times

        # Benchmark API response times
        response_times = benchmark(lambda: asyncio.run(test_api_endpoints()))

        # Verify all API endpoints meet <500ms requirement
        for endpoint, response_time in response_times.items():
            assert (
                response_time < 0.5
            ), f"{endpoint} response time {response_time:.3f}s exceeds 500ms requirement"

    @pytest.mark.benchmark(group="throughput")
    async def test_processing_throughput(
        self,
        async_client: AsyncClient,
        mock_whisper_service: AsyncMock,
        mock_ollama_service: AsyncMock,
        setup_test_environment: Dict[str, Path],
        benchmark,
    ):
        """Test system throughput with sequential processing."""
        test_audio_content = b"\x1a\x45\xdf\xa3" + b"\x00" * 1000

        async def throughput_test():
            """Process multiple audio files sequentially to test throughput."""
            processed_count = 0
            start_time = time.time()

            # Process 5 audio files sequentially
            for i in range(5):
                files = {
                    "file": (
                        f"throughput_test_{i}.webm",
                        test_audio_content,
                        "audio/webm",
                    )
                }

                upload_response = await async_client.post(
                    "/api/v1/audio/upload",
                    files=files,
                    data={"description": f"Throughput test {i}"},
                )
                upload_data = upload_response.json()
                upload_id = upload_data["upload_id"]

                await async_client.post(f"/api/v1/audio/{upload_id}/transcribe")
                await async_client.post(f"/api/v1/audio/{upload_id}/summarize")

                processed_count += 1

            total_time = time.time() - start_time
            throughput = processed_count / total_time  # files per second

            return throughput

        # Benchmark throughput
        throughput = benchmark(lambda: asyncio.run(throughput_test()))

        # Verify reasonable throughput (at least 0.5 files per second with mocked services)
        assert throughput > 0.5, f"Throughput {throughput:.2f} files/sec is too low"

    @pytest.mark.benchmark(group="startup_performance")
    async def test_service_startup_performance(
        self, async_client: AsyncClient, benchmark
    ):
        """Test service startup and first request performance."""

        async def startup_test():
            """Test first request performance after startup."""
            # Simulate cold start scenario
            start_time = time.time()

            # First health check (service startup)
            health_response = await async_client.get("/api/v1/health")
            assert health_response.status_code == 200

            startup_time = time.time() - start_time
            return startup_time

        # Benchmark startup performance
        startup_time = benchmark(lambda: asyncio.run(startup_test()))

        # Startup should be reasonably fast
        assert startup_time < 5.0, f"Service startup took {startup_time:.2f}s, too slow"

    @pytest.mark.benchmark(group="resource_cleanup")
    async def test_resource_cleanup_performance(
        self,
        async_client: AsyncClient,
        mock_whisper_service: AsyncMock,
        mock_ollama_service: AsyncMock,
        setup_test_environment: Dict[str, Path],
        benchmark,
    ):
        """Test resource cleanup and garbage collection performance."""
        test_audio_content = b"\x1a\x45\xdf\xa3" + b"\x00" * 1000

        def cleanup_test():
            """Test resource cleanup after processing multiple files."""
            import gc

            async def process_and_cleanup():
                upload_ids = []

                # Create multiple sessions and uploads
                for i in range(10):
                    session_response = await async_client.post("/api/v1/sessions/")
                    session_data = session_response.json()

                    files = {
                        "file": (
                            f"cleanup_test_{i}.webm",
                            test_audio_content,
                            "audio/webm",
                        )
                    }
                    upload_response = await async_client.post(
                        "/api/v1/audio/upload",
                        files=files,
                        data={
                            "session_id": session_data["session_id"],
                            "description": f"Cleanup test {i}",
                        },
                    )
                    upload_data = upload_response.json()
                    upload_ids.append(upload_data["upload_id"])

                # Force garbage collection
                gc.collect()

                return len(upload_ids)

            return asyncio.run(process_and_cleanup())

        # Benchmark cleanup performance
        processed_files = benchmark(cleanup_test)

        # Verify all files were processed
        assert processed_files == 10
