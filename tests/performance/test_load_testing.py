"""Load testing scenarios for voice processing system."""

import asyncio
import random
import time
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.slow
@pytest.mark.benchmark
class TestLoadTesting:
    """Load testing scenarios to validate system under stress."""

    async def test_high_volume_upload_load(
        self,
        async_client: AsyncClient,
        mock_whisper_service: AsyncMock,
        mock_ollama_service: AsyncMock,
        setup_test_environment: Dict[str, Path],
    ):
        """Test system under high volume of concurrent uploads."""
        # Prepare test data
        test_audio_sizes = [
            1024,  # 1KB - very small
            10240,  # 10KB - small
            102400,  # 100KB - medium
            1048576,  # 1MB - large
        ]

        async def upload_audio_file(file_id: int, size: int):
            """Upload a single audio file."""
            audio_content = b"\x1a\x45\xdf\xa3" + b"\x00" * (size - 4)
            files = {"file": (f"load_test_{file_id}.webm", audio_content, "audio/webm")}

            try:
                response = await async_client.post(
                    "/api/v1/audio/upload",
                    files=files,
                    data={"description": f"Load test file {file_id}"},
                )
                return {
                    "file_id": file_id,
                    "status_code": response.status_code,
                    "success": response.status_code == 201,
                    "response_time": response.elapsed.total_seconds(),
                }
            except Exception as e:
                return {
                    "file_id": file_id,
                    "status_code": 500,
                    "success": False,
                    "error": str(e),
                    "response_time": None,
                }

        # Generate 50 concurrent upload tasks with random sizes
        upload_tasks = []
        for i in range(50):
            size = random.choice(test_audio_sizes)
            upload_tasks.append(upload_audio_file(i, size))

        # Execute all uploads concurrently
        start_time = time.time()
        results = await asyncio.gather(*upload_tasks, return_exceptions=True)
        total_time = time.time() - start_time

        # Analyze results
        successful_uploads = [
            r for r in results if isinstance(r, dict) and r.get("success", False)
        ]
        failed_uploads = [
            r for r in results if not (isinstance(r, dict) and r.get("success", False))
        ]

        # Assertions
        assert (
            len(successful_uploads) >= 40
        ), f"Only {len(successful_uploads)}/50 uploads succeeded"
        assert len(failed_uploads) <= 10, f"Too many failures: {len(failed_uploads)}"
        assert total_time < 30.0, f"Load test took {total_time:.2f}s, too slow"

        # Check response times
        response_times = [
            r["response_time"] for r in successful_uploads if r.get("response_time")
        ]
        if response_times:
            avg_response_time = sum(response_times) / len(response_times)
            assert (
                avg_response_time < 2.0
            ), f"Average response time {avg_response_time:.2f}s too high"

    async def test_sustained_processing_load(
        self,
        async_client: AsyncClient,
        mock_whisper_service: AsyncMock,
        mock_ollama_service: AsyncMock,
        setup_test_environment: Dict[str, Path],
    ):
        """Test sustained processing load over extended period."""
        test_audio_content = b"\x1a\x45\xdf\xa3" + b"\x00" * 1000

        async def process_audio_workflow(workflow_id: int):
            """Complete audio processing workflow."""
            try:
                # Upload
                files = {
                    "file": (
                        f"sustained_{workflow_id}.webm",
                        test_audio_content,
                        "audio/webm",
                    )
                }
                upload_response = await async_client.post(
                    "/api/v1/audio/upload",
                    files=files,
                    data={"description": f"Sustained test {workflow_id}"},
                )

                if upload_response.status_code != 201:
                    return {
                        "workflow_id": workflow_id,
                        "success": False,
                        "stage": "upload",
                    }

                upload_data = upload_response.json()
                upload_id = upload_data["upload_id"]

                # Transcribe
                transcription_response = await async_client.post(
                    f"/api/v1/audio/{upload_id}/transcribe"
                )
                if transcription_response.status_code != 200:
                    return {
                        "workflow_id": workflow_id,
                        "success": False,
                        "stage": "transcription",
                    }

                # Summarize
                summary_response = await async_client.post(
                    f"/api/v1/audio/{upload_id}/summarize"
                )
                if summary_response.status_code != 200:
                    return {
                        "workflow_id": workflow_id,
                        "success": False,
                        "stage": "summarization",
                    }

                return {
                    "workflow_id": workflow_id,
                    "success": True,
                    "upload_id": upload_id,
                }

            except Exception as e:
                return {"workflow_id": workflow_id, "success": False, "error": str(e)}

        # Run sustained load for 2 minutes with staggered starts
        duration = 120  # 2 minutes
        start_time = time.time()
        completed_workflows = []
        workflow_id = 0

        while time.time() - start_time < duration:
            # Start new workflows every 2 seconds
            batch_size = 3  # 3 concurrent workflows per batch
            batch_tasks = []

            for _ in range(batch_size):
                batch_tasks.append(process_audio_workflow(workflow_id))
                workflow_id += 1

            # Wait for batch to complete
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            completed_workflows.extend(
                [r for r in batch_results if isinstance(r, dict)]
            )

            # Small delay between batches
            await asyncio.sleep(2)

        # Analyze sustained load results
        successful_workflows = [
            w for w in completed_workflows if w.get("success", False)
        ]
        failed_workflows = [
            w for w in completed_workflows if not w.get("success", False)
        ]

        total_workflows = len(completed_workflows)
        success_rate = (
            len(successful_workflows) / total_workflows if total_workflows > 0 else 0
        )

        # Assertions for sustained load
        assert total_workflows >= 50, f"Too few workflows completed: {total_workflows}"
        assert success_rate >= 0.9, f"Success rate {success_rate:.2%} too low"
        assert (
            len(failed_workflows) <= total_workflows * 0.1
        ), "Too many failures during sustained load"

    async def test_session_management_load(
        self, async_client: AsyncClient, setup_test_environment: Dict[str, Path]
    ):
        """Test session management under load."""

        async def session_workflow(session_id: int):
            """Complete session-based workflow."""
            try:
                # Create session
                session_response = await async_client.post("/api/v1/sessions/")
                if session_response.status_code != 201:
                    return {
                        "session_id": session_id,
                        "success": False,
                        "stage": "create",
                    }

                session_data = session_response.json()
                actual_session_id = session_data["session_id"]

                # Update session multiple times (simulating editing)
                for update_num in range(3):
                    update_data = {
                        "transcription": f"Updated transcription {update_num} for session {session_id}",
                        "summary": f"- Update {update_num} summary point",
                        "keywords": [f"update{update_num}", "session", "test"],
                    }

                    update_response = await async_client.put(
                        f"/api/v1/sessions/{actual_session_id}/update", json=update_data
                    )

                    if update_response.status_code != 200:
                        return {
                            "session_id": session_id,
                            "success": False,
                            "stage": f"update_{update_num}",
                        }

                # Get session state
                get_response = await async_client.get(
                    f"/api/v1/sessions/{actual_session_id}"
                )
                if get_response.status_code != 200:
                    return {"session_id": session_id, "success": False, "stage": "get"}

                # Complete session
                complete_response = await async_client.post(
                    f"/api/v1/sessions/{actual_session_id}/complete"
                )
                if complete_response.status_code not in [200, 201]:
                    return {
                        "session_id": session_id,
                        "success": False,
                        "stage": "complete",
                    }

                return {
                    "session_id": session_id,
                    "success": True,
                    "actual_session_id": actual_session_id,
                }

            except Exception as e:
                return {"session_id": session_id, "success": False, "error": str(e)}

        # Create 30 concurrent session workflows
        session_tasks = [session_workflow(i) for i in range(30)]

        start_time = time.time()
        session_results = await asyncio.gather(*session_tasks, return_exceptions=True)
        total_time = time.time() - start_time

        # Analyze session load results
        successful_sessions = [
            s
            for s in session_results
            if isinstance(s, dict) and s.get("success", False)
        ]
        failed_sessions = [
            s
            for s in session_results
            if not (isinstance(s, dict) and s.get("success", False))
        ]

        success_rate = len(successful_sessions) / len(session_results)

        # Assertions
        assert success_rate >= 0.9, f"Session success rate {success_rate:.2%} too low"
        assert (
            len(failed_sessions) <= 3
        ), f"Too many session failures: {len(failed_sessions)}"
        assert total_time < 45.0, f"Session load test took {total_time:.2f}s, too slow"

    async def test_mixed_workload_stress(
        self,
        async_client: AsyncClient,
        mock_whisper_service: AsyncMock,
        mock_ollama_service: AsyncMock,
        setup_test_environment: Dict[str, Path],
    ):
        """Test mixed workload with different types of operations."""
        test_audio_content = b"\x1a\x45\xdf\xa3" + b"\x00" * 1000

        async def health_check_worker():
            """Continuous health checks."""
            checks = []
            for _ in range(20):
                try:
                    response = await async_client.get("/api/v1/health")
                    checks.append(response.status_code == 200)
                    await asyncio.sleep(0.5)
                except:
                    checks.append(False)
            return sum(checks)

        async def upload_worker(worker_id: int):
            """Upload worker with various file sizes."""
            uploads = []
            sizes = [1024, 10240, 102400]  # 1KB, 10KB, 100KB

            for i in range(5):
                size = random.choice(sizes)
                audio_content = b"\x1a\x45\xdf\xa3" + b"\x00" * (size - 4)
                files = {
                    "file": (f"mixed_{worker_id}_{i}.webm", audio_content, "audio/webm")
                }

                try:
                    response = await async_client.post(
                        "/api/v1/audio/upload",
                        files=files,
                        data={"description": f"Mixed workload {worker_id}-{i}"},
                    )
                    uploads.append(response.status_code == 201)
                    await asyncio.sleep(random.uniform(0.1, 0.5))
                except:
                    uploads.append(False)

            return sum(uploads)

        async def session_worker(worker_id: int):
            """Session management worker."""
            sessions = []

            for i in range(3):
                try:
                    # Create session
                    session_response = await async_client.post("/api/v1/sessions/")
                    if session_response.status_code == 201:
                        session_data = session_response.json()
                        session_id = session_data["session_id"]

                        # Quick update
                        await async_client.put(
                            f"/api/v1/sessions/{session_id}/update",
                            json={
                                "transcription": f"Mixed workload session {worker_id}-{i}"
                            },
                        )

                        sessions.append(True)
                    else:
                        sessions.append(False)

                    await asyncio.sleep(random.uniform(0.2, 0.8))
                except:
                    sessions.append(False)

            return sum(sessions)

        # Start mixed workload
        tasks = []

        # 2 health check workers
        tasks.extend([health_check_worker() for _ in range(2)])

        # 5 upload workers
        tasks.extend([upload_worker(i) for i in range(5)])

        # 3 session workers
        tasks.extend([session_worker(i) for i in range(3)])

        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time

        # Analyze mixed workload results
        health_checks = results[0:2]  # First 2 are health check workers
        uploads = results[2:7]  # Next 5 are upload workers
        sessions = results[7:10]  # Last 3 are session workers

        # Calculate success rates
        total_health_checks = (
            sum(health_checks) if all(isinstance(h, int) for h in health_checks) else 0
        )
        total_uploads = sum(uploads) if all(isinstance(u, int) for u in uploads) else 0
        total_sessions = (
            sum(sessions) if all(isinstance(s, int) for s in sessions) else 0
        )

        # Assertions
        assert (
            total_health_checks >= 35
        ), f"Health checks: {total_health_checks}/40 passed"
        assert total_uploads >= 20, f"Uploads: {total_uploads}/25 succeeded"
        assert total_sessions >= 8, f"Sessions: {total_sessions}/9 succeeded"
        assert total_time < 60.0, f"Mixed workload took {total_time:.2f}s, too slow"

    async def test_error_recovery_under_load(
        self, async_client: AsyncClient, setup_test_environment: Dict[str, Path]
    ):
        """Test system recovery under load with simulated failures."""
        test_audio_content = b"\x1a\x45\xdf\xa3" + b"\x00" * 1000

        async def flaky_workflow(workflow_id: int):
            """Workflow that may fail and retry."""
            max_retries = 3

            for attempt in range(max_retries):
                try:
                    # Upload
                    files = {
                        "file": (
                            f"flaky_{workflow_id}_{attempt}.webm",
                            test_audio_content,
                            "audio/webm",
                        )
                    }
                    upload_response = await async_client.post(
                        "/api/v1/audio/upload",
                        files=files,
                        data={
                            "description": f"Flaky workflow {workflow_id} attempt {attempt}"
                        },
                    )

                    if upload_response.status_code == 201:
                        upload_data = upload_response.json()
                        upload_id = upload_data["upload_id"]

                        # Simulate processing with potential failures
                        with patch(
                            "app.services.whisper_model.WhisperModel"
                        ) as mock_whisper:
                            if random.random() < 0.3:  # 30% chance of failure
                                mock_whisper.return_value.transcribe.side_effect = (
                                    Exception("Random failure")
                                )
                            else:
                                mock_whisper.return_value.transcribe.return_value = {
                                    "text": f"Transcription for flaky workflow {workflow_id}",
                                    "segments": [
                                        {
                                            "start": 0.0,
                                            "end": 3.0,
                                            "text": "Test transcription",
                                        }
                                    ],
                                }

                            transcription_response = await async_client.post(
                                f"/api/v1/audio/{upload_id}/transcribe"
                            )

                            if transcription_response.status_code == 200:
                                return {
                                    "workflow_id": workflow_id,
                                    "success": True,
                                    "attempts": attempt + 1,
                                }

                    # Wait before retry
                    await asyncio.sleep(0.1)

                except Exception as e:
                    if attempt == max_retries - 1:
                        return {
                            "workflow_id": workflow_id,
                            "success": False,
                            "error": str(e),
                            "attempts": attempt + 1,
                        }

            return {
                "workflow_id": workflow_id,
                "success": False,
                "attempts": max_retries,
            }

        # Run 20 flaky workflows concurrently
        flaky_tasks = [flaky_workflow(i) for i in range(20)]

        start_time = time.time()
        flaky_results = await asyncio.gather(*flaky_tasks, return_exceptions=True)
        total_time = time.time() - start_time

        # Analyze error recovery results
        successful_workflows = [
            w for w in flaky_results if isinstance(w, dict) and w.get("success", False)
        ]
        failed_workflows = [
            w
            for w in flaky_results
            if isinstance(w, dict) and not w.get("success", False)
        ]

        success_rate = len(successful_workflows) / len(flaky_results)
        avg_attempts = sum(
            w.get("attempts", 1) for w in flaky_results if isinstance(w, dict)
        ) / len(flaky_results)

        # Assertions for error recovery
        assert (
            success_rate >= 0.7
        ), f"Error recovery success rate {success_rate:.2%} too low"
        assert avg_attempts <= 2.5, f"Average attempts {avg_attempts:.1f} too high"
        assert (
            total_time < 30.0
        ), f"Error recovery test took {total_time:.2f}s, too slow"
