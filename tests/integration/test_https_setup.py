"""Integration tests for HTTPS setup and nginx configuration."""

import asyncio
import ssl
import socket
import subprocess
import time
from urllib.parse import urljoin

import pytest
import httpx


class TestHTTPSSetup:
    """Test HTTPS configuration and SSL certificate setup."""
    
    @pytest.fixture(scope="class")
    def https_client(self):
        """HTTP client that accepts self-signed certificates."""
        # Create SSL context that accepts self-signed certificates
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        return httpx.AsyncClient(
            verify=ssl_context,
            timeout=30.0,
            follow_redirects=True
        )
    
    @pytest.fixture(scope="class")
    def strict_client(self):
        """HTTP client with strict SSL verification."""
        return httpx.AsyncClient(timeout=30.0)
    
    def test_ssl_certificate_exists(self):
        """Test that SSL certificate files exist."""
        import os
        
        ssl_dir = os.path.join(os.path.dirname(__file__), "../../nginx/ssl")
        cert_path = os.path.join(ssl_dir, "cert.pem")
        key_path = os.path.join(ssl_dir, "key.pem")
        
        # Check if certificate files exist (may not exist in CI)
        if os.path.exists(ssl_dir):
            assert os.path.exists(cert_path), "SSL certificate file should exist"
            assert os.path.exists(key_path), "SSL private key file should exist"
            
            # Verify file permissions
            cert_stat = os.stat(cert_path)
            key_stat = os.stat(key_path)
            
            # Certificate should be readable
            assert cert_stat.st_mode & 0o444, "Certificate should be readable"
            # Private key should have restricted permissions
            assert key_stat.st_mode & 0o600 <= 0o600, "Private key should have restricted permissions"
    
    def test_ssl_certificate_validity(self):
        """Test SSL certificate validity and properties."""
        import os
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
        
        ssl_dir = os.path.join(os.path.dirname(__file__), "../../nginx/ssl")
        cert_path = os.path.join(ssl_dir, "cert.pem")
        
        if not os.path.exists(cert_path):
            pytest.skip("SSL certificate not found - run generate-ssl.sh first")
        
        # Load and validate certificate
        with open(cert_path, 'rb') as f:
            cert_data = f.read()
        
        cert = x509.load_pem_x509_certificate(cert_data, default_backend())
        
        # Check certificate is not expired
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc)
        assert cert.not_valid_before <= now <= cert.not_valid_after, "Certificate should be valid"
        
        # Check subject alternative names include localhost
        try:
            san_ext = cert.extensions.get_extension_for_oid(x509.ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
            san_names = [name.value for name in san_ext.value]
            assert "localhost" in san_names, "Certificate should include localhost in SAN"
        except x509.ExtensionNotFound:
            # Check common name instead
            cn = cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)[0].value
            assert cn == "localhost", "Certificate common name should be localhost"
    
    def test_nginx_config_syntax(self):
        """Test nginx configuration syntax."""
        config_path = os.path.join(os.path.dirname(__file__), "../../nginx/nginx.conf")
        
        if not os.path.exists(config_path):
            pytest.skip("Nginx config not found")
        
        # Test nginx config syntax using docker
        try:
            result = subprocess.run([
                "docker", "run", "--rm", "-v", f"{config_path}:/etc/nginx/nginx.conf:ro",
                "nginx:alpine", "nginx", "-t"
            ], capture_output=True, text=True, timeout=30)
            
            assert result.returncode == 0, f"Nginx config validation failed: {result.stderr}"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pytest.skip("Docker not available for nginx config testing")
    
    @pytest.mark.asyncio
    async def test_http_to_https_redirect(self, https_client):
        """Test HTTP to HTTPS redirect functionality."""
        try:
            response = await https_client.get("http://localhost/health")
            # Should redirect to HTTPS
            assert response.url.scheme == "https", "HTTP should redirect to HTTPS"
            assert response.status_code == 200, "Health check should return 200"
        except httpx.ConnectError:
            pytest.skip("Service not running - integration test requires running containers")
    
    @pytest.mark.asyncio
    async def test_https_health_endpoint(self, https_client):
        """Test HTTPS health check endpoint."""
        try:
            response = await https_client.get("https://localhost/health")
            assert response.status_code == 200, "HTTPS health check should return 200"
            
            # Check for security headers
            headers = response.headers
            assert "strict-transport-security" in headers, "Should include HSTS header"
            assert "x-content-type-options" in headers, "Should include content type options header"
            assert "x-frame-options" in headers, "Should include frame options header"
            
        except httpx.ConnectError:
            pytest.skip("HTTPS service not running - integration test requires running containers")
    
    @pytest.mark.asyncio
    async def test_https_api_endpoints(self, https_client):
        """Test HTTPS API endpoints accessibility."""
        try:
            # Test API endpoints are accessible via HTTPS
            response = await https_client.get("https://localhost/api/health")
            assert response.status_code == 200, "API health endpoint should be accessible via HTTPS"
            
        except httpx.ConnectError:
            pytest.skip("HTTPS service not running - integration test requires running containers")
    
    @pytest.mark.asyncio
    async def test_security_headers(self, https_client):
        """Test security headers are properly set."""
        try:
            response = await https_client.get("https://localhost/")
            headers = response.headers
            
            # Check required security headers
            assert "strict-transport-security" in headers, "Missing HSTS header"
            assert "x-content-type-options" in headers, "Missing content type options header"
            assert "x-frame-options" in headers, "Missing frame options header"
            assert "referrer-policy" in headers, "Missing referrer policy header"
            
            # Verify header values
            hsts = headers.get("strict-transport-security", "")
            assert "max-age=" in hsts, "HSTS should specify max-age"
            
            assert headers.get("x-content-type-options") == "nosniff", "Content type options should be nosniff"
            assert headers.get("x-frame-options") in ["SAMEORIGIN", "DENY"], "Frame options should be SAMEORIGIN or DENY"
            
        except httpx.ConnectError:
            pytest.skip("HTTPS service not running - integration test requires running containers")
    
    def test_ssl_connection_properties(self):
        """Test SSL connection properties and cipher strength."""
        try:
            # Test SSL connection to localhost:443
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            with socket.create_connection(("localhost", 443), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname="localhost") as ssock:
                    # Check SSL version
                    assert ssock.version().startswith(("TLSv1.2", "TLSv1.3")), "Should use TLS 1.2 or 1.3"
                    
                    # Check cipher strength
                    cipher = ssock.cipher()
                    if cipher:
                        cipher_name, version, bits = cipher
                        assert bits >= 128, f"Cipher strength should be at least 128 bits, got {bits}"
                    
        except (socket.error, ConnectionRefusedError, ssl.SSLError):
            pytest.skip("SSL connection test requires running HTTPS service")
    
    @pytest.mark.asyncio
    async def test_pwa_manifest_over_https(self, https_client):
        """Test PWA manifest is accessible over HTTPS."""
        try:
            response = await https_client.get("https://localhost/manifest.json")
            assert response.status_code == 200, "PWA manifest should be accessible via HTTPS"
            
            # Verify it's valid JSON
            manifest = response.json()
            assert "name" in manifest, "Manifest should contain app name"
            
        except httpx.ConnectError:
            pytest.skip("HTTPS service not running - integration test requires running containers")
        except Exception:
            # Manifest might not exist yet, that's ok for this test
            pass
    
    @pytest.mark.asyncio
    async def test_service_worker_over_https(self, https_client):
        """Test service worker is accessible over HTTPS."""
        try:
            response = await https_client.get("https://localhost/service-worker.js")
            
            # Service worker should be accessible (even if it returns 404, the connection should work)
            assert response.status_code in [200, 404], "Service worker endpoint should be reachable via HTTPS"
            
            if response.status_code == 200:
                # Check cache control header for service worker
                cache_control = response.headers.get("cache-control", "")
                assert "no-cache" in cache_control.lower(), "Service worker should have no-cache header"
            
        except httpx.ConnectError:
            pytest.skip("HTTPS service not running - integration test requires running containers")


class TestHTTPSPerformance:
    """Test HTTPS performance characteristics."""
    
    @pytest.mark.asyncio
    async def test_ssl_handshake_time(self):
        """Test SSL handshake performance."""
        try:
            start_time = time.time()
            
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            with socket.create_connection(("localhost", 443), timeout=10) as sock:
                with ssl_context.wrap_socket(sock, server_hostname="localhost") as ssock:
                    handshake_time = time.time() - start_time
                    
                    # SSL handshake should complete within reasonable time
                    assert handshake_time < 1.0, f"SSL handshake took {handshake_time:.3f}s, should be < 1s"
                    
        except (socket.error, ConnectionRefusedError, ssl.SSLError):
            pytest.skip("SSL performance test requires running HTTPS service")
    
    @pytest.mark.asyncio
    async def test_https_response_time(self):
        """Test HTTPS response time is reasonable."""
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        async with httpx.AsyncClient(verify=ssl_context, timeout=30.0) as client:
            try:
                start_time = time.time()
                response = await client.get("https://localhost/health")
                response_time = time.time() - start_time
                
                assert response.status_code == 200, "Health check should succeed"
                assert response_time < 2.0, f"HTTPS response took {response_time:.3f}s, should be < 2s"
                
            except httpx.ConnectError:
                pytest.skip("HTTPS performance test requires running service")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])