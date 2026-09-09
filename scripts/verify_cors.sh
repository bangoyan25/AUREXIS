#!/usr/bin/env bash
# CORS + Login test script
echo "=== CORS preflight test ==="
curl -s -I -X OPTIONS \
  -H 'Origin: https://web.aurexis.web.id' \
  -H 'Access-Control-Request-Method: POST' \
  -H 'Access-Control-Request-Headers: Content-Type,Authorization' \
  https://app.aurexis.web.id/api/v1/auth/login

echo ""
echo "=== Login with bad credentials (expect 401 with CORS headers) ==="
curl -s -w "\n=== HTTP Status: %{http_code} ===\n" \
  -X POST \
  -H 'Content-Type: application/json' \
  -H 'Origin: https://web.aurexis.web.id' \
  -d '{"email":"invalid@aurexis.com","password":"wrongpassword"}' \
  https://app.aurexis.web.id/api/v1/auth/login

echo ""
echo "=== Nginx error log (last 30) ==="
sudo tail -n 30 /var/log/nginx/error.log

echo ""
echo "=== Frontend journal (last 20) ==="
sudo journalctl -u aurexis-frontend -n 20 --no-pager
