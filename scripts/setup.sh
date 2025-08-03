#!/bin/bash
# Enhanced setup script for Dialtone - supports development and production modes

set -e  # Exit on error

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source utilities
source "$SCRIPT_DIR/setup/utils.sh"

# Default mode
MODE="development"
HELP=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--development)
            MODE="development"
            shift
            ;;
        -p|--production)
            MODE="production"
            shift
            ;;
        -h|--help)
            HELP=true
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            HELP=true
            shift
            ;;
    esac
done

# Show help message
show_help() {
    echo ""
    echo "🎵 Dialtone Setup Script"
    echo "======================="
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -d, --development    Setup development environment (default)"
    echo "  -p, --production     Setup production environment with wizard"
    echo "  -h, --help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                   # Development setup"
    echo "  $0 --development     # Development setup (explicit)"
    echo "  $0 --production      # Production setup with configuration wizard"
    echo ""
    echo "Development Mode:"
    echo "  - Sets up local development environment"
    echo "  - Creates Python virtual environment"
    echo "  - Installs development dependencies"
    echo "  - Runs code quality checks"
    echo "  - Starts services with Docker Compose"
    echo ""
    echo "Production Mode:"
    echo "  - Runs interactive configuration wizard"
    echo "  - Sets up production-ready Docker configuration"
    echo "  - Configures SSL certificates (optional)"
    echo "  - Sets up monitoring and maintenance"
    echo "  - Optimizes for performance and security"
    echo ""
    echo "For more information, see: docs/deployment/"
    echo ""
}

# Show help if requested
if [[ "$HELP" == true ]]; then
    show_help
    exit 0
fi

# Welcome message
echo ""
echo "🎵 Dialtone Setup Script"
echo "======================="
echo ""
echo "Mode: $MODE"
echo "Date: $(date)"
echo ""

# Check if setup scripts exist
if [[ ! -f "$SCRIPT_DIR/setup/${MODE}.sh" ]]; then
    log_error "Setup script for mode '$MODE' not found: $SCRIPT_DIR/setup/${MODE}.sh"
    exit 1
fi

# Run the appropriate setup script
log_info "Running $MODE setup..."
echo ""

# Make setup scripts executable
chmod +x "$SCRIPT_DIR/setup/"*.sh

# Execute the setup script
if "$SCRIPT_DIR/setup/${MODE}.sh"; then
    echo ""
    log_success "$MODE setup completed successfully!"
    
    # Show additional information based on mode
    if [[ "$MODE" == "development" ]]; then
        echo ""
        log_info "Development environment is ready for coding!"
        log_info "You can now start developing Dialtone features."
    else
        echo ""
        log_info "Production environment is ready for use!"
        log_info "Dialtone is now accessible to users."
    fi
    
    echo ""
    log_info "For troubleshooting, check the logs in the logs/ directory"
    log_info "For help, see: docs/deployment/ or CLAUDE.md"
    echo ""
else
    echo ""
    log_error "$MODE setup failed!"
    log_info "Check the error messages above for details"
    log_info "You can re-run the setup script after fixing the issues"
    echo ""
    exit 1
fi