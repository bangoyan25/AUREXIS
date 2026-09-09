#!/usr/bin/env bash
set -euo pipefail

echo "=== [1] Stripping CR from transferred files ==="
sed -i 's/\r//' /tmp/aurexis-frontend.service /tmp/web.aurexis.web.id.conf

echo "=== [2] Updating systemd service with HOSTNAME=127.0.0.1 ==="
sudo cp /tmp/aurexis-frontend.service /etc/systemd/system/aurexis-frontend.service
sudo systemctl daemon-reload
sudo systemctl restart aurexis-frontend

echo "=== [3] Waiting for service to start ==="
sleep 4
sudo systemctl status aurexis-frontend --no-pager

echo "=== [4] Verifying port 3000 is localhost-only ==="
sudo ss -lntp | grep ':3000'

echo "=== [5] Testing local Next.js response ==="
curl -s -I http://127.0.0.1:3000/ | head -5

echo "=== [6] Installing clean HTTPS Nginx config ==="
sudo cp /tmp/web.aurexis.web.id.conf /etc/nginx/sites-available/web.aurexis.web.id
sudo nginx -t
sudo systemctl reload nginx

echo "=== [7] Verifying HTTP redirect ==="
curl -s -I http://web.aurexis.web.id | head -5

echo "=== [8] Verifying HTTPS frontend ==="
curl -s -I https://web.aurexis.web.id | head -5

echo "=== [9] Verifying backend still healthy ==="
curl -s -I https://app.aurexis.web.id/api/v1/health | head -5

echo "=== [10] Checking CORS from frontend origin ==="
curl -s -I -X OPTIONS \
  -H "Origin: https://web.aurexis.web.id" \
  -H "Access-Control-Request-Method: POST" \
  https://app.aurexis.web.id/api/v1/auth/login | grep -i "access-control" || true

echo "=== All done! ==="
