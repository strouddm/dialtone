#!/usr/bin/env python3
"""Test script to validate API documentation examples."""

import sys

import requests

BASE_URL = "http://localhost:8000"


def test_root_endpoint():
    """Test the root endpoint."""
    print("Testing root endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/")
        response.raise_for_status()
        data = response.json()

        required_fields = [
            "name",
            "version",
            "description",
            "docs",
            "health",
            "endpoints",
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

        print("✅ Root endpoint working")
        return True
    except Exception as e:
        print(f"❌ Root endpoint failed: {e}")
        return False


def test_health_endpoint():
    """Test the health endpoint."""
    print("Testing health endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        response.raise_for_status()
        data = response.json()

        required_fields = ["status", "timestamp", "version", "uptime_seconds"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

        print(f"✅ Health endpoint working (status: {data['status']})")
        return True
    except Exception as e:
        print(f"❌ Health endpoint failed: {e}")
        return False


def test_ready_endpoint():
    """Test the readiness endpoint."""
    print("Testing readiness endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/ready")
        response.raise_for_status()
        data = response.json()

        required_fields = ["ready", "vault_accessible"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

        ready_status = "✅" if data["ready"] else "⚠️"
        print(f"{ready_status} Readiness endpoint working (ready: {data['ready']})")
        return True
    except Exception as e:
        print(f"❌ Readiness endpoint failed: {e}")
        return False


def test_openapi_schema():
    """Test that OpenAPI schema is available."""
    print("Testing OpenAPI schema...")
    try:
        response = requests.get(f"{BASE_URL}/openapi.json")
        response.raise_for_status()
        schema = response.json()

        required_fields = ["openapi", "info", "paths"]
        for field in required_fields:
            assert field in schema, f"Missing field: {field}"

        # Check that our endpoints are documented
        paths = schema["paths"]
        expected_paths = [
            "/",
            "/health",
            "/ready",
            "/api/v1/audio/upload",
            "/api/v1/audio/transcribe",
        ]

        for path in expected_paths:
            assert path in paths, f"Missing documented path: {path}"

        print("✅ OpenAPI schema valid")
        return True
    except Exception as e:
        print(f"❌ OpenAPI schema failed: {e}")
        return False


def test_upload_endpoint_validation():
    """Test upload endpoint validation (without actual file)."""
    print("Testing upload endpoint validation...")
    try:
        # Test missing file
        response = requests.post(f"{BASE_URL}/api/v1/audio/upload")
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"

        print("✅ Upload validation working")
        return True
    except Exception as e:
        print(f"❌ Upload validation failed: {e}")
        return False


def test_transcribe_endpoint_validation():
    """Test transcribe endpoint validation."""
    print("Testing transcribe endpoint validation...")
    try:
        # Test missing upload_id
        response = requests.post(f"{BASE_URL}/api/v1/audio/transcribe", json={})
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"

        # Test invalid upload_id
        response = requests.post(
            f"{BASE_URL}/api/v1/audio/transcribe", json={"upload_id": "invalid_id"}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"

        print("✅ Transcribe validation working")
        return True
    except Exception as e:
        print(f"❌ Transcribe validation failed: {e}")
        return False


def main():
    """Run all tests."""
    print("🧪 Testing API Documentation Examples")
    print("=" * 50)

    tests = [
        test_root_endpoint,
        test_health_endpoint,
        test_ready_endpoint,
        test_openapi_schema,
        test_upload_endpoint_validation,
        test_transcribe_endpoint_validation,
    ]

    results = []
    for test in tests:
        results.append(test())
        print()

    passed = sum(results)
    total = len(results)

    print("=" * 50)
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All documentation examples are working!")
        return 0
    else:
        print("❌ Some tests failed. Check API server status.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
