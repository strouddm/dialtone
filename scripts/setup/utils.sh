#!/bin/bash
# Common utility functions for Dialtone setup scripts

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

log_step() {
    echo -e "${BLUE}🔄 $1${NC}"
}

# Progress indicator
show_progress() {
    local current=$1
    local total=$2
    local description=$3
    local percentage=$((current * 100 / total))
    echo -e "${BLUE}[$current/$total] ($percentage%) $description${NC}"
}

# Check if command exists
command_exists() {
    command -v "$1" &> /dev/null
}

# Check if port is available
port_available() {
    local port=$1
    ! nc -z localhost "$port" 2>/dev/null
}

# Get system memory in GB
get_system_memory_gb() {
    local memory_kb
    if [[ "$OSTYPE" == "darwin"* ]]; then
        memory_kb=$(sysctl -n hw.memsize | awk '{print int($1/1024/1024)}')
    else
        memory_kb=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    fi
    echo $((memory_kb / 1024 / 1024))
}

# Get available disk space in GB
get_available_disk_gb() {
    local disk_space
    if [[ "$OSTYPE" == "darwin"* ]]; then
        disk_space=$(df -g . | tail -n1 | awk '{print $4}')
    else
        disk_space=$(df -BG . | tail -n1 | awk '{print $4}' | sed 's/G//')
    fi
    echo "$disk_space"
}

# Create backup of file with timestamp
backup_file() {
    local file=$1
    if [[ -f "$file" ]]; then
        local backup_name="${file}.backup.$(date +%Y%m%d_%H%M%S)"
        cp "$file" "$backup_name"
        log_info "Backed up $file to $backup_name"
        echo "$backup_name"
    fi
}

# Restore file from backup
restore_file() {
    local backup_file=$1
    local original_file=${backup_file%.backup.*}
    if [[ -f "$backup_file" ]]; then
        cp "$backup_file" "$original_file"
        log_success "Restored $original_file from backup"
        return 0
    else
        log_error "Backup file $backup_file not found"
        return 1
    fi
}

# Wait for service to be healthy
wait_for_service() {
    local url=$1
    local max_attempts=${2:-30}
    local wait_seconds=${3:-2}
    
    log_step "Waiting for service at $url to be healthy..."
    
    for i in $(seq 1 "$max_attempts"); do
        if curl -f "$url" &> /dev/null; then
            log_success "Service is healthy!"
            return 0
        fi
        echo "Attempt $i/$max_attempts - waiting ${wait_seconds}s..."
        sleep "$wait_seconds"
    done
    
    log_error "Service at $url failed to become healthy after $((max_attempts * wait_seconds)) seconds"
    return 1
}

# Generate random string
generate_random_string() {
    local length=${1:-32}
    openssl rand -hex "$((length / 2))"
}

# Check if running as root
is_root() {
    [[ $EUID -eq 0 ]]
}

# Check if directory is writable
is_writable() {
    local dir=$1
    [[ -w "$dir" ]]
}

# Create directory with proper permissions
create_directory() {
    local dir=$1
    local mode=${2:-755}
    
    if [[ ! -d "$dir" ]]; then
        mkdir -p "$dir"
        chmod "$mode" "$dir"
        log_success "Created directory: $dir"
    else
        log_info "Directory already exists: $dir"
    fi
}

# Download file with retry
download_file() {
    local url=$1
    local output=$2
    local max_attempts=${3:-3}
    
    for i in $(seq 1 "$max_attempts"); do
        if curl -fSL "$url" -o "$output"; then
            log_success "Downloaded $url to $output"
            return 0
        else
            log_warning "Download attempt $i/$max_attempts failed"
            [[ $i -lt $max_attempts ]] && sleep 2
        fi
    done
    
    log_error "Failed to download $url after $max_attempts attempts"
    return 1
}

# Check Docker version compatibility
check_docker_version() {
    local min_version="20.10"
    local docker_version
    
    if ! command_exists docker; then
        log_error "Docker is not installed"
        return 1
    fi
    
    docker_version=$(docker --version | grep -oE '[0-9]+\.[0-9]+' | head -1)
    
    if [[ "$(printf '%s\n' "$min_version" "$docker_version" | sort -V | head -n1)" != "$min_version" ]]; then
        log_error "Docker version $docker_version is too old. Minimum required: $min_version"
        return 1
    fi
    
    log_success "Docker version $docker_version is compatible"
    return 0
}

# Check Docker Compose version
check_docker_compose_version() {
    if ! command_exists docker-compose && ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not available"
        return 1
    fi
    
    log_success "Docker Compose is available"
    return 0
}

# Cleanup function for trap
cleanup() {
    local exit_code=$?
    if [[ $exit_code -ne 0 ]]; then
        log_error "Setup failed with exit code $exit_code"
        log_info "Check the logs for details"
    fi
    exit $exit_code
}

# Set trap for cleanup
trap cleanup EXIT