#!/bin/bash
# System validation functions for Dialtone setup

# Source utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/utils.sh"

# Validate system requirements for development
validate_development_requirements() {
    log_step "Validating development requirements..."
    
    local errors=0
    
    # Check Docker
    if ! check_docker_version; then
        echo "Install Docker: https://docs.docker.com/get-docker/"
        ((errors++))
    fi
    
    # Check Docker Compose
    if ! check_docker_compose_version; then
        echo "Install Docker Compose: https://docs.docker.com/compose/install/"
        ((errors++))
    fi
    
    # Check Python
    if ! command_exists python3; then
        log_error "Python 3 is not installed"
        echo "Install Python 3.11+: https://www.python.org/downloads/"
        ((errors++))
    else
        local python_version
        python_version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        local required_version="3.11"
        
        if [[ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]]; then
            log_error "Python $python_version is installed, but $required_version+ is required"
            ((errors++))
        else
            log_success "Python $python_version is compatible"
        fi
    fi
    
    # Check available disk space (minimum 5GB for development)
    local available_disk
    available_disk=$(get_available_disk_gb)
    if [[ $available_disk -lt 5 ]]; then
        log_error "Insufficient disk space: ${available_disk}GB available, 5GB required"
        ((errors++))
    else
        log_success "Sufficient disk space: ${available_disk}GB available"
    fi
    
    return $errors
}

# Validate system requirements for production
validate_production_requirements() {
    log_step "Validating production requirements..."
    
    local errors=0
    
    # Check Docker
    if ! check_docker_version; then
        echo "Install Docker: https://docs.docker.com/get-docker/"
        ((errors++))
    fi
    
    # Check Docker Compose
    if ! check_docker_compose_version; then
        echo "Install Docker Compose: https://docs.docker.com/compose/install/"
        ((errors++))
    fi
    
    # Check system memory (minimum 8GB for production)
    local system_memory
    system_memory=$(get_system_memory_gb)
    if [[ $system_memory -lt 8 ]]; then
        log_error "Insufficient memory: ${system_memory}GB available, 8GB required for AI models"
        log_warning "Consider using a smaller Whisper model or adding more RAM"
        ((errors++))
    else
        log_success "Sufficient memory: ${system_memory}GB available"
    fi
    
    # Check available disk space (minimum 10GB for production)
    local available_disk
    available_disk=$(get_available_disk_gb)
    if [[ $available_disk -lt 10 ]]; then
        log_error "Insufficient disk space: ${available_disk}GB available, 10GB required"
        echo "This includes space for Docker images, models, and data storage"
        ((errors++))
    else
        log_success "Sufficient disk space: ${available_disk}GB available"
    fi
    
    # Check if running as root (not recommended for production)
    if is_root; then
        log_warning "Running as root is not recommended for production"
        log_info "Consider creating a dedicated user account"
    fi
    
    return $errors
}

# Validate port availability
validate_port_availability() {
    local mode=$1
    local errors=0
    
    log_step "Checking port availability..."
    
    # Required ports for development
    local dev_ports=(8000)
    # Additional ports for production
    local prod_ports=(80 443)
    
    local ports_to_check=("${dev_ports[@]}")
    if [[ "$mode" == "production" ]]; then
        ports_to_check+=("${prod_ports[@]}")
    fi
    
    for port in "${ports_to_check[@]}"; do
        if ! port_available "$port"; then
            log_error "Port $port is already in use"
            log_info "Check what's using port $port: sudo lsof -i :$port"
            ((errors++))
        else
            log_success "Port $port is available"
        fi
    done
    
    return $errors
}

# Validate Obsidian vault path
validate_vault_path() {
    local vault_path=$1
    
    if [[ -z "$vault_path" ]]; then
        log_error "Obsidian vault path is not specified"
        return 1
    fi
    
    if [[ ! -d "$vault_path" ]]; then
        log_error "Obsidian vault directory does not exist: $vault_path"
        log_info "Create the directory or specify a different path"
        return 1
    fi
    
    if ! is_writable "$vault_path"; then
        log_error "Obsidian vault directory is not writable: $vault_path"
        log_info "Check directory permissions"
        return 1
    fi
    
    # Test writing a file
    local test_file="$vault_path/.dialtone_test_$(date +%s)"
    if echo "test" > "$test_file" 2>/dev/null; then
        rm -f "$test_file"
        log_success "Obsidian vault path is valid and writable: $vault_path"
        return 0
    else
        log_error "Cannot write to Obsidian vault directory: $vault_path"
        return 1
    fi
}

# Validate domain name (for SSL setup)
validate_domain() {
    local domain=$1
    
    if [[ -z "$domain" ]]; then
        return 0  # Domain is optional
    fi
    
    # Basic domain validation regex
    if [[ $domain =~ ^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$ ]]; then
        log_success "Domain name format is valid: $domain"
        
        # Check if domain resolves to this server
        local domain_ip
        domain_ip=$(dig +short "$domain" | tail -n1)
        local server_ip
        server_ip=$(curl -s https://ipinfo.io/ip)
        
        if [[ "$domain_ip" == "$server_ip" ]]; then
            log_success "Domain $domain resolves to this server ($server_ip)"
        else
            log_warning "Domain $domain resolves to $domain_ip, but server IP is $server_ip"
            log_info "SSL certificate generation may fail if DNS is not configured correctly"
        fi
        
        return 0
    else
        log_error "Invalid domain name format: $domain"
        return 1
    fi
}

# Validate network connectivity
validate_network_connectivity() {
    log_step "Checking network connectivity..."
    
    local errors=0
    local test_urls=(
        "https://hub.docker.com"
        "https://github.com"
        "https://huggingface.co"
    )
    
    for url in "${test_urls[@]}"; do
        if curl -f -s --max-time 10 "$url" > /dev/null; then
            log_success "Can reach $url"
        else
            log_warning "Cannot reach $url"
            ((errors++))
        fi
    done
    
    if [[ $errors -gt 0 ]]; then
        log_warning "Some network connectivity issues detected"
        log_info "This may affect model downloads and updates"
    else
        log_success "Network connectivity is good"
    fi
    
    return 0  # Don't fail setup for network issues
}

# Validate Docker daemon
validate_docker_daemon() {
    log_step "Checking Docker daemon..."
    
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running"
        log_info "Start Docker daemon: sudo systemctl start docker"
        return 1
    fi
    
    log_success "Docker daemon is running"
    return 0
}

# Validate existing installation
validate_existing_installation() {
    local mode=$1
    
    if [[ -f "docker-compose.yml" ]] && docker-compose ps 2>/dev/null | grep -q "Up"; then
        log_warning "Existing Dialtone installation detected"
        log_info "Running services will be stopped and updated"
        
        if [[ "$mode" == "production" ]] && [[ ! -f ".env.prod" ]]; then
            log_info "Converting development installation to production"
        fi
        
        return 0
    fi
    
    log_info "No existing installation detected"
    return 0
}

# Run all validations for a specific mode
run_all_validations() {
    local mode=$1
    local vault_path=$2
    local domain=$3
    
    local total_errors=0
    
    # Always validate Docker and basic requirements
    validate_docker_daemon || ((total_errors++))
    
    if [[ "$mode" == "production" ]]; then
        validate_production_requirements || ((total_errors++))
    else
        validate_development_requirements || ((total_errors++))
    fi
    
    validate_port_availability "$mode" || ((total_errors++))
    validate_network_connectivity || ((total_errors++))
    validate_existing_installation "$mode" || ((total_errors++))
    
    # Validate vault path if provided
    if [[ -n "$vault_path" ]]; then
        validate_vault_path "$vault_path" || ((total_errors++))
    fi
    
    # Validate domain if provided (production only)
    if [[ "$mode" == "production" ]] && [[ -n "$domain" ]]; then
        validate_domain "$domain" || ((total_errors++))
    fi
    
    if [[ $total_errors -eq 0 ]]; then
        log_success "All validations passed!"
        return 0
    else
        log_error "$total_errors validation error(s) found"
        return $total_errors
    fi
}