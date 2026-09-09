#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════
# AUREXIS Frontend Deployment Script for Ubuntu VPS (129.225.33.77)
# Run on VPS as: bash ~/AUREXIS/scripts/deploy_frontend_vps.sh
# ═══════════════════════════════════════════════════════════════════════

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND_DIR="$REPO_DIR/frontend"

echo "=== 1. Pulling latest code ==="
cd "$REPO_DIR"
git pull origin main

echo "=== 2. Building Next.js frontend ==="
cd "$FRONTEND_DIR"

# Ensure production environment file is configured
if [[ ! -f ".env.local" ]]; then
    echo "Creating .env.local with production settings..."
    cat << 'EOF' > .env.local
NEXT_PUBLIC_API_BASE_URL=https://app.aurexis.web.id
NEXT_PUBLIC_WS_URL=wss://app.aurexis.web.id
NEXT_PUBLIC_TRADING_MODE=SIMULATION
NODE_ENV=production
EOF
fi

npm ci --prefer-offline || npm install
npm run build

echo "=== 3. Setting up systemd service ==="
sudo cp "$REPO_DIR/scripts/systemd/aurexis-frontend.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable aurexis-frontend
sudo systemctl restart aurexis-frontend

echo "=== 4. Checking frontend service status ==="
sleep 3
sudo systemctl is-active --quiet aurexis-frontend && echo "Service active: YES" || echo "Service active: FAILED"

echo "=== 5. Setting up Nginx virtual host ==="
sudo cp "$REPO_DIR/scripts/nginx/web.aurexis.web.id.conf" /etc/nginx/sites-available/web.aurexis.web.id
sudo ln -sf /etc/nginx/sites-available/web.aurexis.web.id /etc/nginx/sites-enabled/

# Test syntax before reload
sudo nginx -t

echo "=== 6. Issuing SSL Certificate if needed ==="
if [[ ! -d "/etc/letsencrypt/live/web.aurexis.web.id" ]]; then
    echo "Requesting Let's Encrypt certificate..."
    sudo certbot --nginx -d web.aurexis.web.id --non-interactive --agree-tos --email admin@aurexis.web.id || {
        echo "WARNING: SSL certificate issuance failed. Verify DNS record points to $(curl -s ifconfig.me) first."
    }
fi

sudo systemctl reload nginx
echo "=== Frontend Deployment Finished ==="
