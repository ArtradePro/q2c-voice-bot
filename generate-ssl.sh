#!/bin/sh
# Generate a self-signed SSL certificate for initial setup.
# Replace with a proper Let's Encrypt cert for production.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SSL_DIR="$SCRIPT_DIR/nginx/ssl"

mkdir -p "$SSL_DIR"

openssl req -x509 -nodes -days 365 \
  -newkey rsa:2048 \
  -keyout "$SSL_DIR/key.pem" \
  -out "$SSL_DIR/cert.pem" \
  -subj "/C=US/ST=State/L=City/O=Q2C/CN=155.138.229.228"

echo "✅ Self-signed certificate generated in $SSL_DIR"
echo ""
echo "For production, replace with Let's Encrypt:"
echo "  certbot certonly --standalone -d yourdomain.com"
echo "  cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem $SSL_DIR/cert.pem"
echo "  cp /etc/letsencrypt/live/yourdomain.com/privkey.pem $SSL_DIR/key.pem"
