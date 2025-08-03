#!/bin/bash
# Development setup script for Dialtone

# Source utilities and validators
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/utils.sh"
source "$SCRIPT_DIR/validators.sh"

# Development setup function
setup_development() {
    log_info "Setting up Dialtone development environment..."
    
    # Validate development requirements
    show_progress 1 10 "Validating system requirements"
    if ! run_all_validations "development"; then
        log_error "System validation failed. Please fix the issues above and try again."
        exit 1
    fi
    
    # Create .env file if it doesn't exist
    show_progress 2 10 "Creating environment configuration"
    if [[ ! -f .env ]]; then
        if [[ -f .env.example ]]; then
            cp .env.example .env
            log_success "Created .env file from template"
            log_warning "Please edit .env file to set your Obsidian vault path!"
        else
            log_error ".env.example not found"
            exit 1
        fi
    else
        log_info ".env file already exists"
    fi
    
    # Create virtual environment for local development
    show_progress 3 10 "Setting up Python virtual environment"
    if [[ ! -d "venv" ]]; then
        log_step "Creating Python virtual environment..."
        python3 -m venv venv
        log_success "Virtual environment created"
    else
        log_info "Virtual environment already exists"
    fi
    
    # Activate virtual environment
    show_progress 4 10 "Activating virtual environment"
    if [[ -f "venv/bin/activate" ]]; then
        source venv/bin/activate
        log_success "Virtual environment activated"
    else
        log_error "Virtual environment activation script not found"
        exit 1
    fi
    
    # Install development dependencies
    show_progress 5 10 "Installing development dependencies"
    if [[ -f "requirements-dev.txt" ]]; then
        log_step "Upgrading pip..."
        pip install --upgrade pip
        
        log_step "Installing development dependencies..."
        pip install -r requirements-dev.txt
        log_success "Development dependencies installed"
    else
        log_error "requirements-dev.txt not found"
        exit 1
    fi
    
    # Create necessary directories
    show_progress 6 10 "Creating project directories"
    create_directory "logs"
    create_directory "obsidian-vault"  # Default vault location
    
    # Run code quality checks
    show_progress 7 10 "Running code quality checks"
    log_step "Checking code formatting with Black..."
    if black --check app tests 2>/dev/null; then
        log_success "Code formatting is correct"
    else
        log_warning "Code formatting issues found (will not fail setup)"
    fi
    
    log_step "Running type checking with mypy..."
    if mypy app 2>/dev/null; then
        log_success "Type checking passed"
    else
        log_warning "Type checking issues found (will not fail setup)"
    fi
    
    # Build Docker image
    show_progress 8 10 "Building Docker images"
    log_step "Building Docker images..."
    if docker-compose build; then
        log_success "Docker images built successfully"
    else
        log_error "Docker build failed"
        exit 1
    fi
    
    # Run tests
    show_progress 9 10 "Running test suite"
    log_step "Running tests..."
    if pytest tests/ -v --cov=app --cov-report=term-missing 2>/dev/null; then
        log_success "All tests passed"
    else
        log_warning "Some tests failed (will not fail setup)"
    fi
    
    # Start services
    show_progress 10 10 "Starting services"
    log_step "Starting Docker services..."
    if docker-compose up -d; then
        log_success "Services started"
    else
        log_error "Failed to start services"
        exit 1
    fi
    
    # Wait for health check
    log_step "Waiting for API to be healthy..."
    if wait_for_service "http://localhost:8000/health" 30 2; then
        log_success "API is healthy and ready!"
    else
        log_error "API failed to start properly"
        log_info "Check logs with: docker-compose logs -f voice-notes-api"
        exit 1
    fi
    
    # Display final status and instructions
    show_development_completion_message
}

# Show completion message with next steps
show_development_completion_message() {
    echo ""
    echo "🎉 Dialtone development setup complete!"
    echo ""
    echo "📋 Next steps:"
    echo "1. Edit .env file to set your Obsidian vault path"
    echo "2. View API docs: http://localhost:8000/docs"
    echo "3. Check health: http://localhost:8000/health"
    echo "4. View logs: docker-compose logs -f"
    echo ""
    echo "🛠️  Development commands:"
    echo "- Run tests: pytest"
    echo "- Format code: black app tests"
    echo "- Type check: mypy app"
    echo "- Restart services: docker-compose restart"
    echo "- Stop services: docker-compose down"
    echo ""
    
    # Show API status
    if curl -f http://localhost:8000/health &> /dev/null; then
        log_success "API is running at http://localhost:8000"
        echo ""
        echo "🏥 Health Check:"
        curl -s http://localhost:8000/health | python3 -m json.tool 2>/dev/null || echo "Health check available at http://localhost:8000/health"
    else
        log_warning "API is not responding"
        log_info "Check logs with: docker-compose logs"
    fi
    
    echo ""
}

# Cleanup development environment
cleanup_development() {
    log_info "Cleaning up development environment..."
    
    # Stop services
    if [[ -f "docker-compose.yml" ]]; then
        log_step "Stopping Docker services..."
        docker-compose down
        log_success "Services stopped"
    fi
    
    # Optional: Remove virtual environment
    read -p "Remove Python virtual environment? (y/n): " remove_venv
    if [[ "$remove_venv" =~ ^[Yy]$ ]]; then
        if [[ -d "venv" ]]; then
            rm -rf venv
            log_success "Virtual environment removed"
        fi
    fi
    
    # Optional: Remove Docker images
    read -p "Remove Docker images? (y/n): " remove_images
    if [[ "$remove_images" =~ ^[Yy]$ ]]; then
        log_step "Removing Docker images..."
        docker-compose down --rmi all
        log_success "Docker images removed"
    fi
    
    log_success "Development environment cleanup complete"
}

# Run development setup if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    case "${1:-setup}" in
        setup)
            setup_development
            ;;
        cleanup)
            cleanup_development
            ;;
        *)
            echo "Usage: $0 [setup|cleanup]"
            exit 1
            ;;
    esac
fi