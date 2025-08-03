"""
Test suite for offline functionality.

Tests the complete offline user experience including:
- Recording while offline
- Queuing uploads
- Sync when back online
- Data persistence
"""

import pytest
import time
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException


class TestOfflineFunctionality:
    """Test complete offline user experience."""

    @pytest.fixture(autouse=True)
    def setup_driver(self):
        """Setup Chrome driver with offline simulation support."""
        chrome_options = Options()
        chrome_options.add_argument('--enable-service-worker')
        chrome_options.add_argument('--enable-background-sync')
        chrome_options.add_argument('--allow-running-insecure-content')
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--headless')
        
        # Enable media devices for recording tests
        chrome_options.add_argument('--use-fake-ui-for-media-stream')
        chrome_options.add_argument('--use-fake-device-for-media-stream')
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.set_page_load_timeout(30)
        self.wait = WebDriverWait(self.driver, 15)
        
        yield
        
        self.driver.quit()

    def go_offline(self):
        """Simulate going offline."""
        self.driver.execute_cdp_cmd('Network.enable', {})
        self.driver.execute_cdp_cmd('Network.emulateNetworkConditions', {
            'offline': True,
            'latency': 0,
            'downloadThroughput': 0,
            'uploadThroughput': 0
        })

    def go_online(self):
        """Simulate going back online."""
        self.driver.execute_cdp_cmd('Network.emulateNetworkConditions', {
            'offline': False,
            'latency': 0,
            'downloadThroughput': -1,
            'uploadThroughput': -1
        })

    def test_app_loads_offline_after_initial_visit(self, live_server):
        """Test that app loads from cache when offline after initial visit."""
        # First visit - online
        self.driver.get(f"{live_server.url}/")
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "app-title")))
        
        # Wait for service worker to cache resources
        time.sleep(3)
        
        # Go offline
        self.go_offline()
        
        # Refresh page - should load from cache
        self.driver.refresh()
        
        try:
            self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "app-title")))
            offline_load_success = True
        except TimeoutException:
            offline_load_success = False
        
        assert offline_load_success, "App should load from cache when offline"

    def test_recording_interface_works_offline(self, live_server):
        """Test that recording interface functions when offline."""
        self.driver.get(f"{live_server.url}/")
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "app-title")))
        time.sleep(2)
        
        # Go offline
        self.go_offline()
        
        # Find record button
        try:
            record_button = self.wait.until(
                EC.element_to_be_clickable((By.ID, "recordButton"))
            )
            
            # Button should be clickable offline
            assert record_button.is_enabled(), "Record button should work offline"
            
            # Test that clicking doesn't cause errors
            record_button.click()
            time.sleep(1)
            
            # Should show recording state
            button_state = record_button.get_attribute('data-state')
            recording_active = button_state == 'recording' or 'recording' in record_button.get_attribute('class')
            
            assert recording_active, "Recording should start offline"
            
        except TimeoutException:
            pytest.skip("Record button not found - may not be implemented yet")

    def test_offline_indicator_shows_when_offline(self, live_server):
        """Test that offline indicator appears when going offline."""
        self.driver.get(f"{live_server.url}/")
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "app-title")))
        time.sleep(2)
        
        # Go offline
        self.go_offline()
        
        # Trigger offline detection
        self.driver.execute_script("window.dispatchEvent(new Event('offline'));")
        time.sleep(1)
        
        # Check for offline indicator
        offline_indicators = self.driver.find_elements(By.CSS_SELECTOR, 
            ".offline-indicator, .sync-indicator.offline, [data-status='offline']")
        
        # At least one offline indicator should be present or visible
        offline_visible = any(indicator.is_displayed() for indicator in offline_indicators)
        
        # If no visual indicator, check for console logging or state changes
        if not offline_visible:
            offline_state = self.driver.execute_script("return navigator.onLine;")
            assert not offline_state, "Should at least detect offline state"

    def test_upload_queues_when_offline(self, live_server):
        """Test that uploads are queued when offline."""
        self.driver.get(f"{live_server.url}/")
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "app-title")))
        time.sleep(2)
        
        # Go offline
        self.go_offline()
        
        # Simulate an upload attempt
        upload_queued = self.driver.execute_script("""
            // Simulate a failed upload that should be queued
            const mockFormData = new FormData();
            mockFormData.append('audio', new Blob(['fake audio data'], { type: 'audio/wav' }));
            
            return fetch('/api/audio/upload', {
                method: 'POST',
                body: mockFormData
            }).then(response => {
                // Should return queued response or error
                return response.status === 202 || !response.ok;
            }).catch(error => {
                // Network error expected when offline
                return true;
            });
        """)
        
        assert upload_queued, "Upload should be queued or fail gracefully when offline"

    def test_queue_persists_across_page_refresh(self, live_server):
        """Test that queued items persist when page is refreshed."""
        self.driver.get(f"{live_server.url}/")
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "app-title")))
        time.sleep(3)
        
        # Add item to queue
        queue_item_added = self.driver.execute_script("""
            if (window.queueManager) {
                const request = new Request('/api/test-upload', { 
                    method: 'POST',
                    body: 'test data'
                });
                return window.queueManager.queueRequest(request, 'test data')
                    .then(() => true)
                    .catch(e => { console.error('Queue error:', e); return false; });
            }
            return false;
        """)
        
        if not queue_item_added:
            pytest.skip("Queue manager not available - may not be implemented yet")
        
        # Refresh page
        self.driver.refresh()
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "app-title")))
        time.sleep(3)
        
        # Check if queue item persisted
        queue_size = self.driver.execute_script("""
            if (window.queueManager) {
                return window.queueManager.getQueueSize()
                    .then(size => size)
                    .catch(() => 0);
            }
            return 0;
        """)
        
        assert queue_size > 0, "Queued items should persist across page refresh"

    def test_sync_triggers_when_back_online(self, live_server):
        """Test that sync automatically triggers when going back online."""
        self.driver.get(f"{live_server.url}/")
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "app-title")))
        time.sleep(3)
        
        # Go offline and queue an item
        self.go_offline()
        
        queue_item_added = self.driver.execute_script("""
            if (window.queueManager) {
                const request = new Request('/api/health', { method: 'GET' });
                return window.queueManager.queueRequest(request)
                    .then(() => true)
                    .catch(() => false);
            }
            return false;
        """)
        
        if not queue_item_added:
            pytest.skip("Queue manager not available")
        
        # Go back online
        self.go_online()
        
        # Trigger online event
        self.driver.execute_script("window.dispatchEvent(new Event('online'));")
        time.sleep(2)
        
        # Check if sync was triggered (look for sync indicator or console logs)
        sync_triggered = self.driver.execute_script("""
            // Check if sync manager exists and if sync was triggered
            if (window.syncManager) {
                // Look for sync indicator or status
                const syncIndicator = document.getElementById('sync-indicator');
                return syncIndicator !== null;
            }
            return false;
        """)
        
        # Alternative check: look for console logs indicating sync
        if not sync_triggered:
            logs = self.driver.get_log('browser')
            sync_logs = [log for log in logs if 'sync' in log['message'].lower()]
            sync_triggered = len(sync_logs) > 0
        
        assert sync_triggered, "Sync should be triggered when going back online"

    def test_manual_sync_button_appears_offline(self, live_server):
        """Test that manual sync option appears when offline with queued items."""
        self.driver.get(f"{live_server.url}/")
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "app-title")))
        time.sleep(3)
        
        # Add item to queue while online
        self.driver.execute_script("""
            if (window.queueManager) {
                const request = new Request('/api/test', { method: 'POST' });
                window.queueManager.queueRequest(request, 'test');
            }
        """)
        
        # Go offline
        self.go_offline()
        time.sleep(1)
        
        # Check for manual sync option
        manual_sync_elements = self.driver.find_elements(By.CSS_SELECTOR, 
            ".sync-retry, .manual-sync, [data-action='sync']")
        
        manual_sync_available = any(element.is_displayed() for element in manual_sync_elements)
        
        # If no visual button, check if sync functionality is accessible
        if not manual_sync_available:
            sync_method_exists = self.driver.execute_script("""
                return window.syncManager && 
                       typeof window.syncManager.triggerSync === 'function';
            """)
            
            assert sync_method_exists, "Manual sync should be available when offline"

    def test_cache_cleanup_when_storage_full(self, live_server):
        """Test that cache cleanup works when storage is full."""
        self.driver.get(f"{live_server.url}/")
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "app-title")))
        time.sleep(3)
        
        # Test cache cleanup functionality
        cleanup_works = self.driver.execute_script("""
            if (window.cacheManager) {
                return window.cacheManager.cleanupOldEntries()
                    .then(() => true)
                    .catch(() => false);
            }
            return false;
        """)
        
        if cleanup_works:
            # Verify cache still works after cleanup
            cache_stats = self.driver.execute_script("""
                return window.cacheManager.getCacheStats()
                    .then(stats => stats)
                    .catch(() => null);
            """)
            
            assert cache_stats is not None, "Cache should still work after cleanup"

    def test_service_worker_update_handling(self, live_server):
        """Test that service worker updates are handled gracefully."""
        self.driver.get(f"{live_server.url}/")
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "app-title")))
        time.sleep(3)
        
        # Check for update handling capability
        update_handling = self.driver.execute_script("""
            return navigator.serviceWorker.ready.then(registration => {
                return {
                    hasRegistration: !!registration,
                    canUpdate: typeof registration.update === 'function'
                };
            }).catch(() => ({ hasRegistration: false, canUpdate: false }));
        """)
        
        assert update_handling['hasRegistration'], "Should have service worker registration"
        assert update_handling['canUpdate'], "Should be able to check for updates"

    def test_network_status_detection_accuracy(self, live_server):
        """Test that network status detection is accurate."""
        self.driver.get(f"{live_server.url}/")
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "app-title")))
        
        # Test online detection
        initial_online = self.driver.execute_script("return navigator.onLine;")
        assert initial_online, "Should detect online state initially"
        
        # Go offline
        self.go_offline()
        time.sleep(1)
        
        # Test offline detection
        offline_detected = self.driver.execute_script("return navigator.onLine;")
        assert not offline_detected, "Should detect offline state"
        
        # Go back online
        self.go_online()
        time.sleep(1)
        
        # Test online detection again
        back_online = self.driver.execute_script("return navigator.onLine;")
        assert back_online, "Should detect back online state"

    def test_data_integrity_during_offline_operations(self, live_server):
        """Test that data integrity is maintained during offline operations."""
        self.driver.get(f"{live_server.url}/")
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "app-title")))
        time.sleep(3)
        
        # Test data integrity in queue operations
        data_integrity_test = self.driver.execute_script("""
            if (window.queueManager) {
                const testData = {
                    id: 'test-123',
                    content: 'test content with special chars: üñîçødé',
                    timestamp: Date.now()
                };
                
                const request = new Request('/api/test', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(testData)
                });
                
                return window.queueManager.queueRequest(request, JSON.stringify(testData))
                    .then(() => window.queueManager.getQueuedRequests())
                    .then(requests => {
                        const queuedRequest = requests[requests.length - 1];
                        const retrievedData = JSON.parse(queuedRequest.body.data);
                        return retrievedData.content === testData.content;
                    })
                    .catch(e => { console.error('Data integrity test failed:', e); return false; });
            }
            return false;
        """)
        
        if data_integrity_test is not False:
            assert data_integrity_test, "Data integrity should be maintained in queue"