#!/bin/bash
# Interactive configuration wizard for Dialtone setup

# Source utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/utils.sh"

# Configuration variables
VAULT_PATH=""
DOMAIN=""
EMAIL=""
ENABLE_SSL=false
WHISPER_MODEL="base"
OLLAMA_MODEL="llama2:7b"
API_PORT=8000
MAX_UPLOAD_SIZE=52428800
PROCESSING_TIMEOUT=35

# Welcome message
show_welcome() {
    echo ""
    echo "🎵 Welcome to Dialtone Configuration Wizard"
    echo "============================================="
    echo ""
    echo "This wizard will help you configure Dialtone for production deployment."
    echo "You can press Ctrl+C at any time to exit."
    echo ""
}

# Prompt for vault path
prompt_vault_path() {
    echo ""
    log_step "Configuring Obsidian vault integration"
    echo ""
    echo "Dialtone needs access to your Obsidian vault to save processed notes."
    echo ""
    
    while true; do
        read -p "Enter your Obsidian vault path: " vault_input
        
        if [[ -z "$vault_input" ]]; then
            log_warning "Vault path cannot be empty"
            continue
        fi
        
        # Expand ~ to home directory
        vault_input="${vault_input/#\~/$HOME}"
        
        if [[ ! -d "$vault_input" ]]; then
            log_warning "Directory does not exist: $vault_input"
            read -p "Would you like to create this directory? (y/n): " create_dir
            if [[ "$create_dir" =~ ^[Yy]$ ]]; then
                if mkdir -p "$vault_input"; then
                    log_success "Created directory: $vault_input"
                    VAULT_PATH="$vault_input"
                    break
                else
                    log_error "Failed to create directory"
                    continue
                fi
            else
                continue
            fi
        else
            if is_writable "$vault_input"; then
                VAULT_PATH="$vault_input"
                log_success "Vault path configured: $VAULT_PATH"
                break
            else
                log_error "Directory is not writable: $vault_input"
                log_info "Check directory permissions or choose a different path"
                continue
            fi
        fi
    done
}

# Prompt for SSL configuration
prompt_ssl_configuration() {
    echo ""
    log_step "Configuring HTTPS/SSL"
    echo ""
    echo "HTTPS is required for PWA functionality and secure access."
    echo "Dialtone can automatically set up SSL certificates using Let's Encrypt."
    echo ""
    
    read -p "Do you want to enable HTTPS with automatic SSL certificates? (y/n): " enable_ssl_input
    
    if [[ "$enable_ssl_input" =~ ^[Yy]$ ]]; then
        ENABLE_SSL=true
        
        echo ""
        echo "SSL certificate setup requires a domain name pointing to this server."
        echo ""
        
        while true; do
            read -p "Enter your domain name (e.g., dialtone.yourdomain.com): " domain_input
            
            if [[ -z "$domain_input" ]]; then
                log_warning "Domain name cannot be empty for SSL setup"
                continue
            fi
            
            # Basic domain validation
            if [[ $domain_input =~ ^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$ ]]; then
                DOMAIN="$domain_input"
                log_success "Domain configured: $DOMAIN"
                break
            else
                log_error "Invalid domain name format"
                continue
            fi
        done
        
        while true; do
            read -p "Enter your email address for Let's Encrypt notifications: " email_input
            
            if [[ -z "$email_input" ]]; then
                log_warning "Email address is required for Let's Encrypt"
                continue
            fi
            
            # Basic email validation
            if [[ $email_input =~ ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then
                EMAIL="$email_input"
                log_success "Email configured: $EMAIL"
                break
            else
                log_error "Invalid email address format"
                continue
            fi
        done
    else
        ENABLE_SSL=false
        log_info "SSL disabled. Dialtone will run on HTTP only."
        log_warning "PWA features may not work properly without HTTPS"
    fi
}

# Prompt for AI model configuration
prompt_ai_configuration() {
    echo ""
    log_step "Configuring AI models"
    echo ""
    
    # Whisper model selection
    echo "Select Whisper model size:"
    echo "1) tiny   - Fastest, lowest accuracy, ~39MB"
    echo "2) base   - Good balance, ~74MB (recommended)"
    echo "3) small  - Better accuracy, ~244MB"
    echo "4) medium - High accuracy, ~769MB"
    echo "5) large  - Highest accuracy, ~1550MB"
    echo ""
    
    while true; do
        read -p "Choose Whisper model (1-5) [2]: " whisper_choice
        whisper_choice=${whisper_choice:-2}
        
        case $whisper_choice in
            1) WHISPER_MODEL="tiny"; break ;;
            2) WHISPER_MODEL="base"; break ;;
            3) WHISPER_MODEL="small"; break ;;
            4) WHISPER_MODEL="medium"; break ;;
            5) WHISPER_MODEL="large"; break ;;
            *) log_warning "Invalid choice. Please enter 1-5." ;;
        esac
    done
    
    log_success "Whisper model configured: $WHISPER_MODEL"
    
    echo ""
    echo "Select Ollama model for summarization:"
    echo "1) llama2:7b    - Good balance, ~3.8GB (recommended)"
    echo "2) llama2:13b   - Better quality, ~7.3GB"
    echo "3) mistral:7b   - Fast and efficient, ~4.1GB"
    echo "4) codellama:7b - Code-focused, ~3.8GB"
    echo ""
    
    while true; do
        read -p "Choose Ollama model (1-4) [1]: " ollama_choice
        ollama_choice=${ollama_choice:-1}
        
        case $ollama_choice in
            1) OLLAMA_MODEL="llama2:7b"; break ;;
            2) OLLAMA_MODEL="llama2:13b"; break ;;
            3) OLLAMA_MODEL="mistral:7b"; break ;;
            4) OLLAMA_MODEL="codellama:7b"; break ;;
            *) log_warning "Invalid choice. Please enter 1-4." ;;
        esac
    done
    
    log_success "Ollama model configured: $OLLAMA_MODEL"
}

# Prompt for performance settings
prompt_performance_settings() {
    echo ""
    log_step "Configuring performance settings"
    echo ""
    
    local system_memory
    system_memory=$(get_system_memory_gb)
    
    echo "System memory detected: ${system_memory}GB"
    echo ""
    
    # API port
    while true; do
        read -p "API port [8000]: " port_input
        port_input=${port_input:-8000}
        
        if [[ "$port_input" =~ ^[0-9]+$ ]] && [[ $port_input -ge 1024 ]] && [[ $port_input -le 65535 ]]; then
            if port_available "$port_input"; then
                API_PORT="$port_input"
                log_success "API port configured: $API_PORT"
                break
            else
                log_error "Port $port_input is already in use"
                continue
            fi
        else
            log_error "Invalid port number. Please enter a number between 1024-65535."
            continue
        fi
    done
    
    # Max upload size
    echo ""
    echo "Configure maximum audio file upload size:"
    echo "1) 25MB  - Small files only"
    echo "2) 50MB  - Default (recommended)"
    echo "3) 100MB - Large files"
    echo "4) 200MB - Very large files"
    echo ""
    
    while true; do
        read -p "Choose max upload size (1-4) [2]: " size_choice
        size_choice=${size_choice:-2}
        
        case $size_choice in
            1) MAX_UPLOAD_SIZE=26214400; break ;;   # 25MB
            2) MAX_UPLOAD_SIZE=52428800; break ;;   # 50MB
            3) MAX_UPLOAD_SIZE=104857600; break ;;  # 100MB
            4) MAX_UPLOAD_SIZE=209715200; break ;;  # 200MB
            *) log_warning "Invalid choice. Please enter 1-4." ;;
        esac
    done
    
    log_success "Max upload size configured: $((MAX_UPLOAD_SIZE / 1048576))MB"
    
    # Processing timeout
    echo ""
    while true; do
        read -p "Processing timeout in seconds [35]: " timeout_input
        timeout_input=${timeout_input:-35}
        
        if [[ "$timeout_input" =~ ^[0-9]+$ ]] && [[ $timeout_input -ge 10 ]] && [[ $timeout_input -le 300 ]]; then
            PROCESSING_TIMEOUT="$timeout_input"
            log_success "Processing timeout configured: ${PROCESSING_TIMEOUT}s"
            break
        else
            log_error "Invalid timeout. Please enter a number between 10-300 seconds."
            continue
        fi
    done
}

# Show configuration summary
show_configuration_summary() {
    echo ""
    echo "========================================="
    echo "🔧 Configuration Summary"
    echo "========================================="
    echo ""
    echo "📁 Obsidian Vault Path: $VAULT_PATH"
    echo "🔒 HTTPS Enabled: $ENABLE_SSL"
    if [[ "$ENABLE_SSL" == true ]]; then
        echo "🌐 Domain: $DOMAIN"
        echo "📧 Email: $EMAIL"
    fi
    echo "🤖 Whisper Model: $WHISPER_MODEL"
    echo "🧠 Ollama Model: $OLLAMA_MODEL"
    echo "🔌 API Port: $API_PORT"
    echo "📦 Max Upload Size: $((MAX_UPLOAD_SIZE / 1048576))MB"
    echo "⏱️  Processing Timeout: ${PROCESSING_TIMEOUT}s"
    echo ""
    
    read -p "Is this configuration correct? (y/n): " confirm
    
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        return 0
    else
        return 1
    fi
}

# Generate environment file
generate_environment_file() {
    local env_file="$1"
    
    log_step "Generating environment configuration..."
    
    cat > "$env_file" << EOF
# Dialtone Production Configuration
# Generated by setup wizard on $(date)

# Application settings
APP_NAME=Dialtone
APP_VERSION=0.1.0
LOG_LEVEL=INFO

# Paths
OBSIDIAN_VAULT_PATH=$VAULT_PATH

# Processing limits
MAX_UPLOAD_SIZE=$MAX_UPLOAD_SIZE
PROCESSING_TIMEOUT=$PROCESSING_TIMEOUT
MAX_CONCURRENT_REQUESTS=3

# Server settings
API_HOST=0.0.0.0
API_PORT=$API_PORT
WORKERS=1

# AI Models
WHISPER_MODEL_SIZE=$WHISPER_MODEL
OLLAMA_MODEL=$OLLAMA_MODEL
OLLAMA_ENABLED=true

# SSL Configuration
ENABLE_SSL=$ENABLE_SSL
DOMAIN=$DOMAIN
EMAIL=$EMAIL

# Security settings
API_KEY_ENABLED=false
CORS_ORIGINS=["*"]
RATE_LIMIT_ENABLED=true

# Development settings
RELOAD=false
DEBUG=false
TESTING=false
EOF
    
    log_success "Environment configuration saved to $env_file"
}

# Main wizard function
run_configuration_wizard() {
    local env_file=${1:-".env.prod"}
    
    show_welcome
    
    while true; do
        prompt_vault_path
        prompt_ssl_configuration
        prompt_ai_configuration
        prompt_performance_settings
        
        if show_configuration_summary; then
            break
        else
            echo ""
            log_info "Let's reconfigure..."
            echo ""
        fi
    done
    
    generate_environment_file "$env_file"
    
    echo ""
    log_success "Configuration wizard completed!"
    log_info "Configuration saved to $env_file"
    echo ""
    
    return 0
}

# Export configuration variables for use by other scripts
export_configuration() {
    export DIALTONE_VAULT_PATH="$VAULT_PATH"
    export DIALTONE_DOMAIN="$DOMAIN"
    export DIALTONE_EMAIL="$EMAIL"
    export DIALTONE_ENABLE_SSL="$ENABLE_SSL"
    export DIALTONE_WHISPER_MODEL="$WHISPER_MODEL"
    export DIALTONE_OLLAMA_MODEL="$OLLAMA_MODEL"
    export DIALTONE_API_PORT="$API_PORT"
    export DIALTONE_MAX_UPLOAD_SIZE="$MAX_UPLOAD_SIZE"
    export DIALTONE_PROCESSING_TIMEOUT="$PROCESSING_TIMEOUT"
}

# Run wizard if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    run_configuration_wizard "$@"
fi