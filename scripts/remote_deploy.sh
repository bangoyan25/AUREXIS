#!/usr/bin/env bash
set -euo pipefail

echo "=== [1] Cleaning up invalid nginx config ==="
sudo rm -f /etc/nginx/sites-enabled/web.aurexis.web.id /etc/nginx/sites-available/web.aurexis.web.id
sudo nginx -t

echo "=== [2] Installing aurexis-frontend.service ==="
sudo cp /tmp/aurexis-frontend.service /etc/systemd/system/aurexis-frontend.service
sudo systemctl daemon-reload
sudo systemctl enable aurexis-frontend
sudo systemctl restart aurexis-frontend

echo "=== [3] Verifying systemd service and port 3000 ==="
sleep 4
sudo systemctl status aurexis-frontend --no-pager
sudo ss -lntp | grep ':3000' || { echo "ERROR: Port 3000 not listening!"; exit 1; }

echo "=== [4] Testing local Next.js response ==="
curl -s -I http://127.0.0.1:3000/ | head -5

echo "=== [5] Setting up temporary HTTP-only Nginx server for certbot ==="
cat << 'EOF' | sudo tee /etc/nginx/sites-available/web.aurexis.web.id > /dev/null
server {
    listen 80;
    listen [::]:80;
    server_name web.aurexis.web.id;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
        allow all;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/web.aurexis.web.id /etc/nginx/sites-enabled/web.aurexis.web.id
sudo nginx -t
sudo systemctl reload nginx

echo "=== [6] Requesting TLS Certificate via Certbot ==="
if [ ! -d "/etc/letsencrypt/live/web.aurexis.web.id" ]; then
    sudo certbot certonly --webroot -w /var/www/html -d web.aurexis.web.id --non-interactive --agree-tos --email admin@aurexis.web.id
else
    echo "Certificate already exists."
fi

echo "=== [7] Installing production HTTPS Nginx config ==="
sudo cp /tmp/web.aurexis.web.id.conf /etc/nginx/sites-available/web.aurexis.web.id
sudo nginx -t
sudo systemctl reload nginx

echo "=== [8] Final Verification ==="
echo "Testing HTTP -> HTTPS redirect:"
curl -s -I http://web.aurexis.web.id | head -5

echo "Testing HTTPS frontend:"
curl -s -I https://web.aurexis.web.id | head -5

echo "Deployment complete!"
