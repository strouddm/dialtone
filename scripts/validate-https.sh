#!/bin/bash

# Validate HTTPS setup for Dialtone
# This script tests the HTTPS configuration without requiring running containers

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_test() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

run_test() {
    local test_name="$1"
    local test_command="$2"
    
    TESTS_RUN=$((TESTS_RUN + 1))
    log_test "Running: $test_name"
    
    if eval "$test_command" > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} PASS"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "  ${RED}✗${NC} FAIL"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# Test file existence
test_files_exist() {
    log_info "Testing file structure..."
    
    run_test "Nginx configuration exists" "test -f '$PROJECT_DIR/nginx/nginx.conf'"
    run_test "SSL certificate script exists" "test -f '$PROJECT_DIR/scripts/generate-ssl.sh'"
    run_test "Docker compose includes nginx" "grep -q 'nginx:' '$PROJECT_DIR/docker-compose.yml'"
    run_test "Environment example updated" "grep -q 'HTTPS_ENABLED' '$PROJECT_DIR/.env.example'"
}

# Test nginx configuration syntax
test_nginx_config() {
    log_info "Testing nginx configuration..."
    
    local config_file="$PROJECT_DIR/nginx/nginx.conf"
    
    if ! command -v nginx > /dev/null 2>&1; then
        # Try using docker if nginx is not installed locally
        if command -v docker > /dev/null 2>&1; then
            # Test nginx config - upstream resolution failure is expected outside docker-compose
            log_test "Nginx config syntax (docker)"
            TESTS_RUN=$((TESTS_RUN + 1))
            
            output=$(docker run --rm -v "$config_file:/etc/nginx/nginx.conf:ro" nginx:alpine nginx -t 2>&1)
            if echo "$output" | grep -q "host not found in upstream"; then
                echo -e "  ${GREEN}✓${NC} PASS (upstream resolution expected to fail outside docker-compose)"
                TESTS_PASSED=$((TESTS_PASSED + 1))
            elif echo "$output" | grep -q "syntax is ok"; then
                echo -e "  ${GREEN}✓${NC} PASS"
                TESTS_PASSED=$((TESTS_PASSED + 1))
            else
                echo -e "  ${RED}✗${NC} FAIL"
                TESTS_FAILED=$((TESTS_FAILED + 1))
            fi
        else
            log_warn "Neither nginx nor docker available for config validation"
        fi
    else
        run_test "Nginx config syntax (local)" "nginx -t -c '$config_file'"
    fi
    
    # Test configuration contains required directives
    run_test "SSL configuration present" "grep -q 'ssl_certificate' '$config_file'"
    run_test "Security headers configured" "grep -q 'Strict-Transport-Security' '$config_file'"
    run_test "Upstream backend configured" "grep -q 'upstream dialtone_backend' '$config_file'"
    run_test "Rate limiting configured" "grep -q 'limit_req_zone' '$config_file'"
    run_test "Gzip compression enabled" "grep -q 'gzip on' '$config_file'"
}

# Test SSL certificate generation
test_ssl_generation() {
    log_info "Testing SSL certificate generation..."
    
    local ssl_script="$PROJECT_DIR/scripts/generate-ssl.sh"
    local ssl_dir="$PROJECT_DIR/nginx/ssl"
    
    run_test "SSL script is executable" "test -x '$ssl_script'"
    
    # Test help command
    run_test "SSL script help works" "'$ssl_script' help"
    
    # Clean up any existing certificates for test
    if [[ -d "$ssl_dir" ]]; then
        rm -f "$ssl_dir"/*.pem "$ssl_dir"/*.csr
    fi
    
    # Generate test certificate
    if run_test "SSL certificate generation" "'$ssl_script' generate localhost"; then
        run_test "Certificate file created" "test -f '$ssl_dir/cert.pem'"
        run_test "Private key file created" "test -f '$ssl_dir/key.pem'"
        run_test "Certificate permissions correct" "test \$(stat -c '%a' '$ssl_dir/cert.pem') = '644'"
        run_test "Private key permissions correct" "test \$(stat -c '%a' '$ssl_dir/key.pem') = '600'"
        
        # Test certificate verification
        if command -v openssl > /dev/null 2>&1; then
            run_test "Certificate verification" "'$ssl_script' verify"
            run_test "Certificate info accessible" "'$ssl_script' info"
        else
            log_warn "OpenSSL not available for certificate verification"
        fi
    fi
}

# Test docker-compose configuration
test_docker_compose() {
    log_info "Testing Docker Compose configuration..."
    
    local compose_file="$PROJECT_DIR/docker-compose.yml"
    
    if command -v docker-compose > /dev/null 2>&1; then
        run_test "Docker Compose config valid" "cd '$PROJECT_DIR' && docker-compose config > /dev/null"
    elif command -v docker > /dev/null 2>&1 && docker compose version > /dev/null 2>&1; then
        run_test "Docker Compose config valid" "cd '$PROJECT_DIR' && docker compose config > /dev/null"
    else
        log_warn "Docker Compose not available for validation"
    fi
    
    # Test configuration content
    run_test "Nginx service defined" "grep -q 'nginx:' '$compose_file'"
    run_test "Nginx ports exposed" "grep -A 10 'nginx:' '$compose_file' | grep -q '443:443'"
    run_test "SSL volume mounted" "grep -A 20 'nginx:' '$compose_file' | grep -q 'ssl:'"
    run_test "API port not exposed" "! grep -q '8000:8000' '$compose_file'"
    run_test "Nginx depends on API" "grep -A 20 'nginx:' '$compose_file' | grep -q 'voice-notes-api'"
}

# Test environment configuration
test_environment() {
    log_info "Testing environment configuration..."
    
    local env_example="$PROJECT_DIR/.env.example"
    
    run_test "HTTPS configuration in env" "grep -q 'HTTPS_ENABLED' '$env_example'"
    run_test "Domain configuration in env" "grep -q 'DOMAIN_NAME' '$env_example'"
    run_test "SSL email configuration in env" "grep -q 'SSL_EMAIL' '$env_example'"
}

# Test integration test file
test_integration_tests() {
    log_info "Testing integration test setup..."
    
    local test_file="$PROJECT_DIR/tests/integration/test_https_setup.py"
    
    run_test "HTTPS integration tests exist" "test -f '$test_file'"
    
    if command -v python3 > /dev/null 2>&1; then
        run_test "Integration test syntax valid" "python3 -m py_compile '$test_file'"
    else
        log_warn "Python not available for test syntax validation"
    fi
}

# Test runtime connectivity (if service is running)
test_runtime_connectivity() {
    log_info "Testing runtime connectivity (if service is running)..."
    
    # Test if HTTPS port is accessible
    if timeout 2 bash -c "</dev/tcp/localhost/443" 2>/dev/null; then
        run_test "HTTPS port accessible" "timeout 2 bash -c '</dev/tcp/localhost/443'"
        
        # Test HTTPS response (ignore certificate warnings)
        if command -v curl > /dev/null 2>&1; then
            run_test "HTTPS health check" "curl -k -f -s https://localhost/health > /dev/null"
            run_test "HTTP redirects to HTTPS" "curl -s -I http://localhost/ | grep -q '301'"
            run_test "Security headers present" "curl -k -s -I https://localhost/ | grep -i 'strict-transport-security'"
        else
            log_warn "curl not available for runtime connectivity tests"
        fi
    else
        log_warn "HTTPS service not running - skipping runtime tests"
        log_warn "Start the service with: docker-compose up -d"
    fi
}

# Main execution
main() {
    echo -e "${BLUE}======================================${NC}"
    echo -e "${BLUE}  Dialtone HTTPS Setup Validation    ${NC}"
    echo -e "${BLUE}======================================${NC}"
    echo
    
    test_files_exist
    test_nginx_config
    test_ssl_generation
    test_docker_compose
    test_environment
    test_integration_tests
    test_runtime_connectivity
    
    echo
    echo -e "${BLUE}======================================${NC}"
    echo -e "${BLUE}           Test Summary               ${NC}"
    echo -e "${BLUE}======================================${NC}"
    echo -e "Total tests run: ${BLUE}$TESTS_RUN${NC}"
    echo -e "Tests passed: ${GREEN}$TESTS_PASSED${NC}"
    echo -e "Tests failed: ${RED}$TESTS_FAILED${NC}"
    
    if [[ $TESTS_FAILED -eq 0 ]]; then
        echo
        echo -e "${GREEN}✓ All tests passed! HTTPS setup is ready.${NC}"
        echo -e "${GREEN}To start the service with HTTPS:${NC}"
        echo -e "  1. Generate SSL certificates: ./scripts/generate-ssl.sh"
        echo -e "  2. Start services: docker-compose up -d"
        echo -e "  3. Access via: https://localhost/"
        echo
        exit 0
    else
        echo
        echo -e "${RED}✗ Some tests failed. Please check the configuration.${NC}"
        exit 1
    fi
}

# Run main function
main "$@"