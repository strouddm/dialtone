# Nginx Configuration for Dialtone

This directory contains the nginx configuration for running Dialtone with HTTPS support.

## Setup

1. Generate SSL certificates for your domain/IP:
   ```bash
   # For development/testing (self-signed certificate)
   openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
     -keyout nginx/ssl/dialtone.key \
     -out nginx/ssl/dialtone.crt \
     -subj "/CN=localhost"
   
   # Alternative names supported by the base configuration:
   # - cert.pem / key.pem
   ```

2. Update `nginx.conf` with your server name/IP address if needed.

3. Start the services with docker-compose:
   ```bash
   docker-compose up -d
   ```

## Notes

- The nginx service will redirect all HTTP traffic to HTTPS
- SSL certificates should be placed in the `nginx/ssl/` directory
- Never commit SSL certificates to version control
- For production, use proper SSL certificates from a trusted CA