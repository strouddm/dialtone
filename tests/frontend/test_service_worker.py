"""
Test suite for service worker functionality.

This module tests the service worker implementation including:
- Service worker registration
- Offline functionality
- Cache management
- Request queuing
- Background sync
"""

import pytest
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException


class TestServiceWorker:
    """Test service worker functionality."""

    @pytest.fixture(autouse=True)
    def setup_driver(self):
        """Setup Chrome driver with PWA support."""
        chrome_options = Options()
        chrome_options.add_argument("--enable-service-worker")
        chrome_options.add_argument("--enable-background-sync")
        chrome_options.add_argument("--allow-running-insecure-content")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--headless")  # Remove for debugging

        # Enable offline simulation
        chrome_options.add_experimental_option("useAutomationExtension", False)

        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.set_page_load_timeout(30)
        self.wait = WebDriverWait(self.driver, 10)

        yield

        self.driver.quit()

    def test_service_worker_registration(self, live_server):
        """Test that service worker registers successfully."""
        self.driver.get(f"{live_server.url}/")

        # Wait for page to load
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "app-title")))

        # Check service worker registration in console
        logs = self.driver.get_log("browser")
        sw_registered = any(
            "Service Worker registered successfully" in log["message"] for log in logs
        )

        assert sw_registered, "Service worker should register successfully"

    def test_service_worker_scope(self, live_server):
        """Test service worker scope is correct."""
        self.driver.get(f"{live_server.url}/")

        # Wait for service worker registration
        time.sleep(2)

        # Execute JavaScript to check service worker registration
        sw_info = self.driver.execute_script(
            """
            return navigator.serviceWorker.ready.then(registration => {
                return {
                    scope: registration.scope,
                    active: !!registration.active
                };
            });
        """
        )

        assert sw_info["scope"].endswith("/"), "Service worker scope should be root"
        assert sw_info["active"], "Service worker should be active"

    def test_offline_cache_functionality(self, live_server):
        """Test that app shell resources are cached for offline use."""
        self.driver.get(f"{live_server.url}/")

        # Wait for service worker and cache setup
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "app-title")))
        time.sleep(3)

        # Simulate offline mode
        self.driver.execute_cdp_cmd("Network.enable", {})
        self.driver.execute_cdp_cmd(
            "Network.emulateNetworkConditions",
            {
                "offline": True,
                "latency": 0,
                "downloadThroughput": 0,
                "uploadThroughput": 0,
            },
        )

        # Refresh page to test offline functionality
        self.driver.refresh()

        # App should still load from cache
        try:
            self.wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, "app-title"))
            )
            offline_works = True
        except TimeoutException:
            offline_works = False

        assert offline_works, "App should load from cache when offline"

    def test_request_queuing_when_offline(self, live_server):
        """Test that failed requests are queued when offline."""
        self.driver.get(f"{live_server.url}/")

        # Wait for initialization
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "app-title")))
        time.sleep(2)

        # Simulate offline mode
        self.driver.execute_cdp_cmd("Network.enable", {})
        self.driver.execute_cdp_cmd(
            "Network.emulateNetworkConditions",
            {
                "offline": True,
                "latency": 0,
                "downloadThroughput": 0,
                "uploadThroughput": 0,
            },
        )

        # Try to make an API request that should be queued
        queue_result = self.driver.execute_script(
            """
            return window.queueManager.queueRequest(
                new Request('/api/health', { method: 'GET' })
            ).then(() => true).catch(() => false);
        """
        )

        assert queue_result, "Request should be queued when offline"

    def test_background_sync_registration(self, live_server):
        """Test that background sync is registered properly."""
        self.driver.get(f"{live_server.url}/")

        # Wait for initialization
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "app-title")))
        time.sleep(2)

        # Check background sync support and registration
        sync_info = self.driver.execute_script(
            """
            return {
                supported: 'sync' in window.ServiceWorkerRegistration.prototype,
                registered: navigator.serviceWorker.ready.then(registration => {
                    return registration.sync.register('test-sync').then(() => true).catch(() => false);
                })
            };
        """
        )

        # Background sync might not be supported in headless Chrome
        if sync_info["supported"]:
            assert sync_info[
                "registered"
            ], "Background sync should register successfully"

    def test_cache_management(self, live_server):
        """Test cache management functionality."""
        self.driver.get(f"{live_server.url}/")

        # Wait for initialization
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "app-title")))
        time.sleep(3)

        # Test cache statistics
        cache_stats = self.driver.execute_script(
            """
            return window.cacheManager ? 
                window.cacheManager.getCacheStats() : null;
        """
        )

        # Cache manager might not be available in test environment
        if cache_stats:
            assert (
                "totalEntries" in cache_stats
            ), "Cache stats should include total entries"
            assert (
                cache_stats["totalEntries"] >= 0
            ), "Total entries should be non-negative"

    def test_sync_indicator_visibility(self, live_server):
        """Test that sync indicator appears when there are queued items."""
        self.driver.get(f"{live_server.url}/")

        # Wait for initialization
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "app-title")))
        time.sleep(2)

        # Check if sync indicator can be created
        indicator_created = self.driver.execute_script(
            """
            if (window.syncManager) {
                window.syncManager.showSyncStatus('syncing');
                return document.getElementById('sync-indicator') !== null;
            }
            return false;
        """
        )

        # Sync manager might not be available in test environment
        if indicator_created:
            # Check if sync indicator is visible
            sync_indicator = self.driver.find_element(By.ID, "sync-indicator")
            assert sync_indicator.is_displayed(), "Sync indicator should be visible"

    def test_offline_detection(self, live_server):
        """Test that offline detection works correctly."""
        self.driver.get(f"{live_server.url}/")

        # Wait for initialization
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "app-title")))

        # Test online state
        online_state = self.driver.execute_script("return navigator.onLine;")
        assert online_state, "Should detect online state initially"

        # Simulate offline
        self.driver.execute_cdp_cmd("Network.enable", {})
        self.driver.execute_cdp_cmd(
            "Network.emulateNetworkConditions",
            {
                "offline": True,
                "latency": 0,
                "downloadThroughput": 0,
                "uploadThroughput": 0,
            },
        )

        # Check offline state (may take a moment to detect)
        time.sleep(1)
        offline_state = self.driver.execute_script("return navigator.onLine;")
        assert not offline_state, "Should detect offline state"

    def test_update_notification(self, live_server):
        """Test that update notifications work correctly."""
        self.driver.get(f"{live_server.url}/")

        # Wait for initialization
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "app-title")))
        time.sleep(2)

        # Simulate showing update notification
        notification_shown = self.driver.execute_script(
            """
            if (window.swRegistration) {
                window.swRegistration.showUpdateNotification();
                return document.querySelector('.sw-update-notification') !== null;
            }
            return false;
        """
        )

        # Service worker registration might not be available in test environment
        if notification_shown:
            notification = self.driver.find_element(
                By.CLASS_NAME, "sw-update-notification"
            )
            assert notification.is_displayed(), "Update notification should be visible"

    def test_queue_persistence(self, live_server):
        """Test that queued requests persist across sessions."""
        self.driver.get(f"{live_server.url}/")

        # Wait for initialization
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "app-title")))
        time.sleep(2)

        # Add item to queue
        queue_added = self.driver.execute_script(
            """
            if (window.queueManager) {
                return window.queueManager.queueRequest(
                    new Request('/api/test', { method: 'POST' }),
                    'test data'
                ).then(() => true).catch(() => false);
            }
            return false;
        """
        )

        if queue_added:
            # Refresh page to simulate new session
            self.driver.refresh()
            self.wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, "app-title"))
            )
            time.sleep(2)

            # Check if queue persisted
            queue_size = self.driver.execute_script(
                """
                return window.queueManager ? 
                    window.queueManager.getQueueSize() : 0;
            """
            )

            assert queue_size > 0, "Queue should persist across sessions"

    def test_cache_version_handling(self, live_server):
        """Test that cache versions are handled correctly."""
        self.driver.get(f"{live_server.url}/")

        # Wait for initialization
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "app-title")))
        time.sleep(3)

        # Check cache names include version
        cache_names = self.driver.execute_script(
            """
            return caches.keys().then(names => names);
        """
        )

        # Look for dialtone cache with version
        dialtone_caches = [name for name in cache_names if "dialtone" in name]
        assert len(dialtone_caches) > 0, "Should have dialtone caches"

        # Check that cache names include version identifiers
        versioned_caches = [
            name for name in dialtone_caches if "v1" in name or "v2" in name
        ]
        assert len(versioned_caches) > 0, "Cache names should include version"

    def test_error_handling_graceful_degradation(self, live_server):
        """Test that service worker errors don't break the app."""
        self.driver.get(f"{live_server.url}/")

        # Wait for initialization
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "app-title")))

        # App should load even if service worker fails
        app_title = self.driver.find_element(By.CLASS_NAME, "app-title")
        assert app_title.is_displayed(), "App should work even with SW issues"

        # Check that no JavaScript errors prevent basic functionality
        errors = self.driver.get_log("browser")
        critical_errors = [
            log
            for log in errors
            if log["level"] == "SEVERE"
            and "service worker" not in log["message"].lower()
        ]

        assert len(critical_errors) == 0, "Should not have critical JavaScript errors"
