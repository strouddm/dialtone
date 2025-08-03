#!/bin/bash

# Generate SSL certificates for local development
# This script creates self-signed certificates for HTTPS setup

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SSL_DIR="$PROJECT_DIR/nginx/ssl"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

# Function to generate self-signed certificate
generate_self_signed() {
    local domain=${1:-localhost}
    
    log_info "Generating self-signed SSL certificate for $domain..."
    
    # Create SSL directory if it doesn't exist
    mkdir -p "$SSL_DIR"
    
    # Generate private key
    openssl genrsa -out "$SSL_DIR/key.pem" 2048
    
    # Generate certificate signing request
    openssl req -new -key "$SSL_DIR/key.pem" -out "$SSL_DIR/cert.csr" \
        -subj "/C=US/ST=Development/L=Development/O=Dialtone/OU=Development/CN=$domain"
    
    # Generate self-signed certificate valid for 365 days
    openssl x509 -req -in "$SSL_DIR/cert.csr" -signkey "$SSL_DIR/key.pem" \
        -out "$SSL_DIR/cert.pem" -days 365 \
        -extensions v3_req -extfile <(cat <<EOF
[v3_req]
keyUsage = keyEncipherment, dataEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = $domain
DNS.2 = localhost
DNS.3 = *.localhost
IP.1 = 127.0.0.1
IP.2 = ::1
EOF
)
    
    # Clean up CSR file
    rm "$SSL_DIR/cert.csr"
    
    # Set appropriate permissions
    chmod 600 "$SSL_DIR/key.pem"
    chmod 644 "$SSL_DIR/cert.pem"
    
    log_info "SSL certificate generated successfully!"
    log_info "Certificate: $SSL_DIR/cert.pem"
    log_info "Private key: $SSL_DIR/key.pem"
    log_warn "Note: This is a self-signed certificate for development only."
    log_warn "Browsers will show security warnings until you add it to trusted certificates."
}

# Function to show certificate info
show_cert_info() {
    if [[ -f "$SSL_DIR/cert.pem" ]]; then
        log_info "Certificate information:"
        openssl x509 -in "$SSL_DIR/cert.pem" -text -noout | grep -E "(Subject:|Issuer:|Not Before:|Not After:|DNS:|IP Address:)"
    else
        log_error "Certificate not found at $SSL_DIR/cert.pem"
        return 1
    fi
}

# Function to verify certificate
verify_cert() {
    if [[ -f "$SSL_DIR/cert.pem" && -f "$SSL_DIR/key.pem" ]]; then
        log_info "Verifying certificate and key match..."
        
        cert_hash=$(openssl x509 -noout -modulus -in "$SSL_DIR/cert.pem" | openssl md5)
        key_hash=$(openssl rsa -noout -modulus -in "$SSL_DIR/key.pem" | openssl md5)
        
        if [[ "$cert_hash" == "$key_hash" ]]; then
            log_info "Certificate and key match successfully!"
            return 0
        else
            log_error "Certificate and key do not match!"
            return 1
        fi
    else
        log_error "Certificate or key file not found"
        return 1
    fi
}

# Function to install certificate in system (optional)
install_cert_instructions() {
    cat << EOF

${GREEN}To trust this certificate in your browser:${NC}

${YELLOW}Chrome/Edge (Linux):${NC}
1. Go to chrome://settings/certificates
2. Click "Authorities" tab
3. Click "Import" and select: $SSL_DIR/cert.pem
4. Check "Trust this certificate for identifying websites"

${YELLOW}Firefox:${NC}
1. Go to about:preferences#privacy
2. Scroll to "Certificates" and click "View Certificates"
3. Click "Authorities" tab, then "Import"
4. Select: $SSL_DIR/cert.pem
5. Check "Trust this CA to identify websites"

${YELLOW}macOS:${NC}
sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain $SSL_DIR/cert.pem

${YELLOW}Linux (system-wide):${NC}
sudo cp $SSL_DIR/cert.pem /usr/local/share/ca-certificates/dialtone.crt
sudo update-ca-certificates

EOF
}

# Main script logic
case "${1:-generate}" in
    "generate")
        domain=${2:-localhost}
        generate_self_signed "$domain"
        install_cert_instructions
        ;;
    "info")
        show_cert_info
        ;;
    "verify")
        verify_cert
        ;;
    "help"|"-h"|"--help")
        cat << EOF
Usage: $0 [command] [domain]

Commands:
    generate [domain]  Generate self-signed SSL certificate (default: localhost)
    info              Show certificate information
    verify            Verify certificate and key match
    help              Show this help message

Examples:
    $0 generate               # Generate cert for localhost
    $0 generate mydomain.com  # Generate cert for custom domain
    $0 info                   # Show certificate details
    $0 verify                 # Verify cert/key pair

EOF
        ;;
    *)
        log_error "Unknown command: $1"
        log_info "Use '$0 help' for usage information"
        exit 1
        ;;
esac