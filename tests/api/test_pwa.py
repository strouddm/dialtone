"""Tests for PWA functionality."""

import json

import pytest
from fastapi.testclient import TestClient


class TestPWAManifest:
    """Test PWA manifest serving and configuration."""

    def test_manifest_endpoint(self, client: TestClient):
        """Test manifest.json is served correctly."""
        response = client.get("/static/manifest.json")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

        manifest = response.json()
        assert manifest["name"] == "Dialtone Voice Notes"
        assert manifest["short_name"] == "Dialtone"
        assert manifest["display"] == "standalone"
        assert manifest["theme_color"] == "#7c3aed"
        assert manifest["background_color"] == "#1a1a1a"
        assert len(manifest["icons"]) >= 2

    def test_manifest_required_fields(self, client: TestClient):
        """Test manifest has all required PWA fields."""
        response = client.get("/static/manifest.json")
        manifest = response.json()

        # Required fields for PWA
        required_fields = [
            "name",
            "short_name",
            "start_url",
            "display",
            "icons",
            "theme_color",
            "background_color",
        ]

        for field in required_fields:
            assert field in manifest, f"Missing required field: {field}"

    def test_manifest_icons(self, client: TestClient):
        """Test manifest icon configuration."""
        response = client.get("/static/manifest.json")
        manifest = response.json()

        # Check we have minimum required icon sizes
        icon_sizes = {icon["sizes"] for icon in manifest["icons"]}
        assert "192x192" in icon_sizes, "Missing required 192x192 icon"
        assert "512x512" in icon_sizes, "Missing required 512x512 icon"

        # Check maskable icons
        maskable_icons = [
            icon for icon in manifest["icons"] if icon.get("purpose") == "maskable"
        ]
        assert len(maskable_icons) >= 2, "Should have at least 2 maskable icons"

    def test_manifest_shortcuts(self, client: TestClient):
        """Test manifest app shortcuts."""
        response = client.get("/static/manifest.json")
        manifest = response.json()

        assert "shortcuts" in manifest
        assert len(manifest["shortcuts"]) > 0

        # Check first shortcut
        shortcut = manifest["shortcuts"][0]
        assert shortcut["name"] == "New Recording"
        assert shortcut["url"] == "/?action=record"
        assert len(shortcut["icons"]) > 0


class TestPWAIntegration:
    """Test PWA integration in HTML."""

    def test_pwa_meta_tags(self, client: TestClient):
        """Test PWA meta tags are present in HTML."""
        response = client.get("/")
        assert response.status_code == 200

        html = response.text

        # Check manifest link
        assert '<link rel="manifest" href="/static/manifest.json">' in html

        # Check iOS meta tags
        assert "apple-mobile-web-app-capable" in html
        assert "apple-mobile-web-app-title" in html
        assert "apple-touch-icon" in html

        # Check theme color
        assert '<meta name="theme-color" content="#7c3aed">' in html

    def test_pwa_script_loaded(self, client: TestClient):
        """Test PWA JavaScript is loaded."""
        response = client.get("/")
        html = response.text

        assert '<script src="/static/js/pwa.js" defer></script>' in html


class TestPWAAssets:
    """Test PWA asset availability."""

    def test_icon_availability(self, client: TestClient):
        """Test that key PWA icons are available."""
        icon_paths = [
            "/static/assets/icons/icon-192x192.png",
            "/static/assets/icons/icon-512x512.png",
            "/static/assets/icons/icon-192x192-maskable.png",
            "/static/assets/icons/icon-512x512-maskable.png",
        ]

        for path in icon_paths:
            response = client.get(path)
            assert response.status_code == 200, f"Icon not found: {path}"
            assert response.headers["content-type"] == "image/png"

    def test_pwa_javascript(self, client: TestClient):
        """Test PWA JavaScript file is served."""
        response = client.get("/static/js/pwa.js")
        assert response.status_code == 200
        assert "javascript" in response.headers["content-type"]

        # Check for key PWA functionality
        js_content = response.text
        assert "beforeinstallprompt" in js_content
        assert "appinstalled" in js_content
        assert "display-mode: standalone" in js_content
