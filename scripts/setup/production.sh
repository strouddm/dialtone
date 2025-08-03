#!/bin/bash
# Production setup script for Dialtone

# Source utilities, validators, and wizard
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/utils.sh"
source "$SCRIPT_DIR/validators.sh"
source "$SCRIPT_DIR/wizard.sh"

# Production setup function
setup_production() {
    log_info "Setting up Dialtone for production deployment..."
    
    # Run configuration wizard
    show_progress 1 12 "Running configuration wizard"
    if ! run_configuration_wizard ".env.prod"; then
        log_error "Configuration wizard failed"
        exit 1
    fi
    
    # Source the generated configuration
    if [[ -f ".env.prod" ]]; then
        source .env.prod
        export_configuration
    else
        log_error "Production configuration file not found"
        exit 1
    fi
    
    # Validate production requirements with configuration
    show_progress 2 12 "Validating production requirements"
    if ! run_all_validations "production" "$OBSIDIAN_VAULT_PATH" "$DOMAIN"; then
        log_error "System validation failed. Please fix the issues above and try again."
        exit 1
    fi
    
    # Backup existing configuration
    show_progress 3 12 "Backing up existing configuration"
    backup_existing_configuration
    
    # Stop existing services if running
    show_progress 4 12 "Stopping existing services"
    stop_existing_services
    
    # Generate production Docker Compose configuration
    show_progress 5 12 "Generating production configuration"
    generate_production_config
    
    # Setup SSL certificates if enabled
    if [[ "$ENABLE_SSL" == "true" ]]; then
        show_progress 6 12 "Setting up SSL certificates"
        setup_ssl_certificates
    else
        show_progress 6 12 "Skipping SSL setup (disabled)"
    fi
    
    # Download and setup AI models
    show_progress 7 12 "Setting up AI models"
    setup_ai_models
    
    # Build production images
    show_progress 8 12 "Building production images"
    build_production_images
    
    # Start production services
    show_progress 9 12 "Starting production services"
    start_production_services
    
    # Validate service health
    show_progress 10 12 "Validating service health"
    validate_service_health
    
    # Run end-to-end tests
    show_progress 11 12 "Running end-to-end validation"
    run_production_validation
    
    # Setup monitoring and maintenance
    show_progress 12 12 "Setting up monitoring"
    setup_monitoring
    
    # Show completion message
    show_production_completion_message
}

# Backup existing configuration
backup_existing_configuration() {
    log_step "Backing up existing configuration..."
    
    local backup_dir="backup_$(date +%Y%m%d_%H%M%S)"
    create_directory "$backup_dir"
    
    # Backup configuration files
    for file in .env docker-compose.yml nginx.conf; do
        if [[ -f "$file" ]]; then
            cp "$file" "$backup_dir/"
            log_info "Backed up $file"
        fi
    done
    
    log_success "Configuration backed up to $backup_dir"
}

# Stop existing services
stop_existing_services() {
    if [[ -f "docker-compose.yml" ]]; then
        log_step "Stopping existing services..."
        docker-compose down || true
        log_success "Existing services stopped"
    else
        log_info "No existing services to stop"
    fi
}

# Generate production configuration files
generate_production_config() {
    log_step "Generating production configuration files..."
    
    # Generate nginx configuration
    generate_nginx_config
    
    # Copy production Docker Compose file
    if [[ -f "$SCRIPT_DIR/../templates/docker-compose.prod.yml" ]]; then
        cp "$SCRIPT_DIR/../templates/docker-compose.prod.yml" "docker-compose.yml"
        log_success "Production Docker Compose configuration ready"
    else
        log_error "Production Docker Compose template not found"
        exit 1
    fi
    
    # Set proper permissions
    chmod 600 .env.prod
    log_success "Production configuration files generated"
}

# Generate nginx configuration
generate_nginx_config() {
    local template_file="$SCRIPT_DIR/../templates/nginx.conf.template"
    local output_file="nginx.conf"
    
    if [[ ! -f "$template_file" ]]; then
        log_error "Nginx configuration template not found"
        exit 1
    fi
    
    # Calculate max upload size in MB
    local max_upload_mb=$((MAX_UPLOAD_SIZE / 1048576))
    
    # Copy template and replace placeholders
    cp "$template_file" "$output_file"
    
    # Replace common placeholders
    sed -i "s/__DOMAIN__/$DOMAIN/g" "$output_file"
    sed -i "s/__MAX_UPLOAD_SIZE_MB__/$max_upload_mb/g" "$output_file"
    
    if [[ "$ENABLE_SSL" == "true" ]]; then
        # Enable SSL redirect
        sed -i 's|__SSL_REDIRECT_BLOCK__|location / { return 301 https://$server_name$request_uri; }|g' "$output_file"
        
        # Add HTTPS server block
        local https_block=$(cat << 'EOF'
server {
    listen 443 ssl http2;
    server_name __DOMAIN__;

    # SSL configuration
    ssl_certificate /etc/letsencrypt/live/__DOMAIN__/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/__DOMAIN__/privkey.pem;
    ssl_session_timeout 1d;
    ssl_session_cache shared:MozTLS:10m;
    ssl_session_tickets off;

    # Modern configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    # HSTS
    add_header Strict-Transport-Security "max-age=63072000" always;

    # Main application
    location / {
        try_files $uri $uri/ @backend;
    }

    # Static files
    location /static/ {
        alias /var/www/html/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # API endpoints
    location /api/ {
        limit_req zone=api burst=20 nodelay;
        proxy_pass http://dialtone_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    # Upload endpoint with special rate limiting
    location /api/audio/upload {
        limit_req zone=upload burst=5 nodelay;
        proxy_pass http://dialtone_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 600s;
        proxy_connect_timeout 75s;
        proxy_request_buffering off;
    }

    # Health check
    location /health {
        proxy_pass http://dialtone_backend;
        access_log off;
    }

    # Fallback to backend
    location @backend {
        proxy_pass http://dialtone_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF
)
        sed -i "s|__HTTPS_SERVER_BLOCK__|$https_block|g" "$output_file"
        sed -i "s/__DOMAIN__/$DOMAIN/g" "$output_file"
    else
        # Remove SSL redirect and HTTPS block
        sed -i 's|__SSL_REDIRECT_BLOCK__||g' "$output_file"
        sed -i 's|__HTTPS_SERVER_BLOCK__||g' "$output_file"
    fi
    
    log_success "Nginx configuration generated"
}

# Setup SSL certificates
setup_ssl_certificates() {
    if [[ "$ENABLE_SSL" != "true" ]] || [[ -z "$DOMAIN" ]]; then
        log_info "SSL setup skipped (not configured)"
        return 0
    fi
    
    log_step "Setting up SSL certificates for $DOMAIN..."
    
    # Create certbot webroot directory
    create_directory "certbot-webroot"
    
    # Start nginx first for Let's Encrypt validation
    log_step "Starting nginx for certificate validation..."
    docker-compose up -d nginx
    
    # Wait for nginx to be ready
    sleep 5
    
    # Run certbot to get certificates
    log_step "Requesting SSL certificate from Let's Encrypt..."
    if docker-compose --profile ssl-setup run --rm certbot; then
        log_success "SSL certificate obtained successfully"
        
        # Restart nginx to use the new certificates
        docker-compose restart nginx
        log_success "Nginx restarted with SSL configuration"
        
        # Setup certificate renewal
        setup_certificate_renewal
    else
        log_error "Failed to obtain SSL certificate"
        log_warning "Falling back to HTTP-only configuration"
        
        # Disable SSL in configuration
        sed -i 's/ENABLE_SSL=true/ENABLE_SSL=false/' .env.prod
        generate_nginx_config
        docker-compose restart nginx
    fi
}

# Setup certificate renewal
setup_certificate_renewal() {
    log_step "Setting up certificate auto-renewal..."
    
    # Create renewal script
    cat > renew-certs.sh << 'EOF'
#!/bin/bash
# SSL certificate renewal script for Dialtone

cd "$(dirname "$0")"
docker-compose --profile ssl-setup run --rm certbot renew
docker-compose restart nginx
EOF
    
    chmod +x renew-certs.sh
    
    # Add to crontab (run daily at 2 AM)
    (crontab -l 2>/dev/null; echo "0 2 * * * $(pwd)/renew-certs.sh >> $(pwd)/logs/cert-renewal.log 2>&1") | crontab -
    
    log_success "Certificate auto-renewal configured"
}

# Setup AI models
setup_ai_models() {
    log_step "Setting up AI models..."
    
    # Start ollama service first
    docker-compose up -d ollama
    
    # Wait for ollama to be ready
    if wait_for_service "http://localhost:11434/api/tags" 60 5; then
        log_success "Ollama service is ready"
        
        # Pull the configured model
        log_step "Downloading $OLLAMA_MODEL model..."
        if docker-compose exec ollama ollama pull "$OLLAMA_MODEL"; then
            log_success "Ollama model downloaded: $OLLAMA_MODEL"
        else
            log_error "Failed to download Ollama model"
            exit 1
        fi
    else
        log_error "Ollama service failed to start"
        exit 1
    fi
}

# Build production images
build_production_images() {
    log_step "Building production Docker images..."
    
    if docker-compose build --no-cache; then
        log_success "Production images built successfully"
    else
        log_error "Failed to build production images"
        exit 1
    fi
}

# Start production services
start_production_services() {
    log_step "Starting production services..."
    
    if docker-compose up -d; then
        log_success "Production services started"
    else
        log_error "Failed to start production services"
        exit 1
    fi
    
    # Wait for all services to be healthy
    log_step "Waiting for services to be healthy..."
    sleep 30
}

# Validate service health
validate_service_health() {
    log_step "Validating service health..."
    
    local errors=0
    
    # Check API health
    local api_url="http://localhost:$API_PORT/health"
    if [[ "$ENABLE_SSL" == "true" ]]; then
        api_url="https://$DOMAIN/health"
    fi
    
    if wait_for_service "$api_url" 30 2; then
        log_success "API service is healthy"
    else
        log_error "API service health check failed"
        ((errors++))
    fi
    
    # Check ollama health
    if wait_for_service "http://localhost:11434/api/tags" 30 2; then
        log_success "Ollama service is healthy"
    else
        log_error "Ollama service health check failed"
        ((errors++))
    fi
    
    # Check nginx health (if SSL enabled)
    if [[ "$ENABLE_SSL" == "true" ]]; then
        if curl -f -s --max-time 10 "https://$DOMAIN" > /dev/null; then
            log_success "Nginx SSL service is healthy"
        else
            log_error "Nginx SSL service health check failed"
            ((errors++))
        fi
    fi
    
    if [[ $errors -eq 0 ]]; then
        log_success "All services are healthy"
        return 0
    else
        log_error "$errors service(s) failed health checks"
        return $errors
    fi
}

# Run production validation tests
run_production_validation() {
    log_step "Running end-to-end validation..."
    
    # Test basic API endpoints
    local base_url="http://localhost:$API_PORT"
    if [[ "$ENABLE_SSL" == "true" ]]; then
        base_url="https://$DOMAIN"
    fi
    
    # Test health endpoint
    if curl -f "$base_url/health" > /dev/null; then
        log_success "Health endpoint accessible"
    else
        log_error "Health endpoint not accessible"
        return 1
    fi
    
    # Test static files
    if curl -f "$base_url/" > /dev/null; then
        log_success "Static files accessible"
    else
        log_warning "Static files may not be accessible"
    fi
    
    log_success "End-to-end validation completed"
}

# Setup monitoring
setup_monitoring() {
    log_step "Setting up monitoring and maintenance..."
    
    # Create monitoring script
    cat > monitor.sh << 'EOF'
#!/bin/bash
# Monitoring script for Dialtone production

# Check service health
echo "=== Service Health Check $(date) ==="
docker-compose ps
echo ""

# Check disk usage
echo "=== Disk Usage ==="
df -h
echo ""

# Check memory usage
echo "=== Memory Usage ==="
free -h
echo ""

# Check logs for errors
echo "=== Recent Errors ==="
docker-compose logs --tail=10 --since="1h" | grep -i error || echo "No recent errors"
echo ""
EOF
    
    chmod +x monitor.sh
    
    # Create maintenance script
    cat > maintenance.sh << 'EOF'
#!/bin/bash
# Maintenance script for Dialtone production

echo "Running maintenance tasks..."

# Clean up old logs
find logs/ -name "*.log*" -mtime +30 -delete 2>/dev/null || true

# Clean up Docker
docker system prune -f

# Update Docker images (commented out - run manually)
# docker-compose pull
# docker-compose up -d

echo "Maintenance completed"
EOF
    
    chmod +x maintenance.sh
    
    # Add monitoring to crontab (run every hour)
    (crontab -l 2>/dev/null; echo "0 * * * * $(pwd)/monitor.sh >> $(pwd)/logs/monitoring.log 2>&1") | crontab -
    
    # Add maintenance to crontab (run weekly)
    (crontab -l 2>/dev/null; echo "0 3 * * 0 $(pwd)/maintenance.sh >> $(pwd)/logs/maintenance.log 2>&1") | crontab -
    
    log_success "Monitoring and maintenance configured"
}

# Show production completion message
show_production_completion_message() {
    echo ""
    echo "🎉 Dialtone production setup complete!"
    echo ""
    echo "🌐 Access Information:"
    if [[ "$ENABLE_SSL" == "true" ]]; then
        echo "   Web Interface: https://$DOMAIN"
        echo "   API Documentation: https://$DOMAIN/docs"
        echo "   Health Check: https://$DOMAIN/health"
    else
        echo "   Web Interface: http://localhost:$API_PORT"
        echo "   API Documentation: http://localhost:$API_PORT/docs"
        echo "   Health Check: http://localhost:$API_PORT/health"
    fi
    echo ""
    echo "📁 Configuration:"
    echo "   Obsidian Vault: $OBSIDIAN_VAULT_PATH"
    echo "   Environment File: .env.prod"
    echo "   Docker Compose: docker-compose.yml"
    echo ""
    echo "🛠️  Management Commands:"
    echo "   View logs: docker-compose logs -f"
    echo "   Restart services: docker-compose restart"
    echo "   Stop services: docker-compose down"
    echo "   Update services: docker-compose pull && docker-compose up -d"
    echo ""
    echo "📊 Monitoring:"
    echo "   Run health check: ./monitor.sh"
    echo "   Run maintenance: ./maintenance.sh"
    echo "   Log files: logs/"
    echo ""
    if [[ "$ENABLE_SSL" == "true" ]]; then
        echo "🔒 SSL Certificate:"
        echo "   Auto-renewal: Configured (daily check at 2 AM)"
        echo "   Manual renewal: ./renew-certs.sh"
        echo ""
    fi
    echo "✅ Production deployment ready!"
    echo ""
}

# Rollback production setup
rollback_production() {
    log_info "Rolling back production setup..."
    
    # Stop services
    docker-compose down
    
    # Restore from backup
    local latest_backup
    latest_backup=$(ls -t backup_* 2>/dev/null | head -1)
    
    if [[ -n "$latest_backup" ]] && [[ -d "$latest_backup" ]]; then
        log_step "Restoring from backup: $latest_backup"
        
        for file in "$latest_backup"/*; do
            if [[ -f "$file" ]]; then
                local filename
                filename=$(basename "$file")
                cp "$file" "$filename"
                log_info "Restored $filename"
            fi
        done
        
        log_success "Configuration restored from backup"
    else
        log_warning "No backup found to restore from"
    fi
    
    # Remove crontab entries
    crontab -l 2>/dev/null | grep -v "$(pwd)" | crontab - 2>/dev/null || true
    
    log_success "Production rollback completed"
}

# Run production setup if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    case "${1:-setup}" in
        setup)
            setup_production
            ;;
        rollback)
            rollback_production
            ;;
        *)
            echo "Usage: $0 [setup|rollback]"
            exit 1
            ;;
    esac
fi