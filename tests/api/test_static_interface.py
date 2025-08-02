"""Tests for the static recording interface."""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path


class TestStaticInterface:
    """Test the recording interface endpoints."""

    def test_root_serves_html(self, client: TestClient):
        """Test that root endpoint serves the HTML interface."""
        response = client.get("/")
        
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")

    def test_api_info_endpoint(self, client: TestClient):
        """Test that /api endpoint returns JSON metadata."""
        response = client.get("/api")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "endpoints" in data
        
        # Check that all expected endpoints are listed
        endpoints = data["endpoints"]
        assert "upload" in endpoints
        assert "transcribe" in endpoints
        assert "sessions" in endpoints
        assert "vault_save" in endpoints

    def test_static_css_served(self, client: TestClient):
        """Test that CSS files are served correctly."""
        response = client.get("/static/css/main.css")
        
        assert response.status_code == 200
        assert "text/css" in response.headers["content-type"]

    def test_static_js_served(self, client: TestClient):
        """Test that JavaScript files are served correctly."""
        response = client.get("/static/js/recorder.js")
        
        assert response.status_code == 200
        assert (
            "application/javascript" in response.headers["content-type"]
            or "text/javascript" in response.headers["content-type"]
        )

    def test_static_js_ui_served(self, client: TestClient):
        """Test that UI JavaScript file is served correctly."""
        response = client.get("/static/js/ui.js")
        
        assert response.status_code == 200
        assert (
            "application/javascript" in response.headers["content-type"]
            or "text/javascript" in response.headers["content-type"]
        )

    def test_static_file_not_found(self, client: TestClient):
        """Test that non-existent static files return 404."""
        response = client.get("/static/nonexistent.js")
        
        assert response.status_code == 404

    def test_html_contains_required_elements(self, client: TestClient):
        """Test that HTML contains required UI elements."""
        response = client.get("/")
        html_content = response.text
        
        # Check for essential HTML structure
        assert "<!DOCTYPE html>" in html_content
        assert '<html lang="en">' in html_content
        assert 'viewport' in html_content
        assert 'Dialtone' in html_content
        
        # Check for recording interface elements
        assert 'record-button' in html_content
        assert 'timer' in html_content
        assert 'status-message' in html_content
        
        # Check for JavaScript includes
        assert '/static/js/recorder.js' in html_content
        assert '/static/js/ui.js' in html_content
        
        # Check for CSS include
        assert '/static/css/main.css' in html_content

    def test_html_mobile_optimized(self, client: TestClient):
        """Test that HTML is mobile-optimized."""
        response = client.get("/")
        html_content = response.text
        
        # Check for mobile viewport
        assert 'width=device-width' in html_content
        assert 'user-scalable=no' in html_content
        
        # Check for PWA meta tags
        assert 'theme-color' in html_content
        assert 'apple-mobile-web-app-capable' in html_content

    def test_cors_headers_present(self, client: TestClient):
        """Test that CORS headers are present for web interface."""
        response = client.get("/")
        
        # Check that response doesn't fail due to CORS issues
        assert response.status_code == 200
        
        # For preflight requests
        options_response = client.options("/api/v1/audio/upload")
        assert options_response.status_code == 200


class TestInterfaceFileStructure:
    """Test that all required static files exist."""

    def test_static_directory_exists(self):
        """Test that static directory exists."""
        static_dir = Path("app/static")
        assert static_dir.exists()
        assert static_dir.is_dir()

    def test_html_file_exists(self):
        """Test that main HTML file exists."""
        html_file = Path("app/static/index.html")
        assert html_file.exists()
        assert html_file.is_file()

    def test_css_directory_exists(self):
        """Test that CSS directory exists."""
        css_dir = Path("app/static/css")
        assert css_dir.exists()
        assert css_dir.is_dir()

    def test_main_css_exists(self):
        """Test that main CSS file exists."""
        css_file = Path("app/static/css/main.css")
        assert css_file.exists()
        assert css_file.is_file()

    def test_js_directory_exists(self):
        """Test that JavaScript directory exists."""
        js_dir = Path("app/static/js")
        assert js_dir.exists()
        assert js_dir.is_dir()

    def test_recorder_js_exists(self):
        """Test that recorder JavaScript file exists."""
        js_file = Path("app/static/js/recorder.js")
        assert js_file.exists()
        assert js_file.is_file()

    def test_ui_js_exists(self):
        """Test that UI JavaScript file exists."""
        js_file = Path("app/static/js/ui.js")
        assert js_file.exists()
        assert js_file.is_file()

    def test_assets_directory_exists(self):
        """Test that assets directory exists."""
        assets_dir = Path("app/static/assets")
        assert assets_dir.exists()
        assert assets_dir.is_dir()


class TestInterfaceContent:
    """Test the content of interface files."""

    def test_css_contains_mobile_styles(self):
        """Test that CSS contains mobile-first styles."""
        css_file = Path("app/static/css/main.css")
        content = css_file.read_text()
        
        # Check for mobile-first approach
        assert "@media (max-width:" in content
        assert "viewport" in content or "vh" in content
        assert "touch-action" in content
        
        # Check for design tokens
        assert ":root" in content
        assert "--color-" in content
        assert "--space-" in content

    def test_recorder_js_contains_required_classes(self):
        """Test that recorder JS contains required functionality."""
        js_file = Path("app/static/js/recorder.js")
        content = js_file.read_text()
        
        # Check for AudioRecorder class
        assert "class AudioRecorder" in content
        assert "MediaRecorder" in content
        assert "getUserMedia" in content
        assert "startRecording" in content
        assert "stopRecording" in content

    def test_ui_js_contains_required_classes(self):
        """Test that UI JS contains required functionality."""
        js_file = Path("app/static/js/ui.js")
        content = js_file.read_text()
        
        # Check for RecorderUI class
        assert "class RecorderUI" in content
        assert "DOMContentLoaded" in content
        assert "addEventListener" in content
        assert "handleRecordClick" in content

    def test_html_accessibility_features(self):
        """Test that HTML includes accessibility features."""
        html_file = Path("app/static/index.html")
        content = html_file.read_text()
        
        # Check for ARIA attributes
        assert "aria-label" in content
        assert "aria-live" in content
        assert "role=" in content
        
        # Check for semantic HTML
        assert "<main" in content
        assert "<section" in content
        assert "<header" in content
        
        # Check for screen reader support
        assert "visually-hidden" in content or "sr-only" in content