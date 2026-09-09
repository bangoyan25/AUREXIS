# AUREXIS — Production VPS Deployment Guide

## Architecture

```
User Browser
    │ HTTPS
    ▼
web.aurexis.web.id (Next.js frontend)
    │ HTTPS API calls
    ▼
app.aurexis.web.id (FastAPI backend)
    │
    ├── PostgreSQL 16
    ├── Redis 7
    └── MT5 Agent WSS (Windows VPS 103.67.244.220)
```

## Server

- Linux VPS: `129.225.33.77`
- OS: Ubuntu 22.04 / 24.04
- Backend: running (systemd: `aurexis-backend`)
- Frontend: deploy as below

---

## Step 1: DNS Record

Add to Cloudflare DNS (aurexis.web.id zone):

| Type | Name | Content | Proxy status |
|------|------|---------|--------------|
| A    | web  | 129.225.33.77 | DNS only (grey cloud) |

Wait for propagation (~1 min to 5 min).

Verify: `nslookup web.aurexis.web.id 8.8.8.8`  
Expected: `129.225.33.77`

---

## Step 2: Backend CORS (Critical)

SSH into `129.225.33.77` and update backend `.env`:

```bash
cd ~/AUREXIS
# Add or update CORS_ORIGINS
sed -i 's|CORS_ORIGINS=.*|CORS_ORIGINS=https://web.aurexis.web.id|' .env

# If CORS_ORIGINS= is empty and was not set, add it:
grep -q "CORS_ORIGINS" .env || echo "CORS_ORIGINS=https://web.aurexis.web.id" >> .env

# Restart backend
sudo systemctl restart aurexis-backend
sudo systemctl is-active aurexis-backend
```

Verify CORS is active:
```bash
curl -s -I -X OPTIONS \
  -H "Origin: https://web.aurexis.web.id" \
  -H "Access-Control-Request-Method: POST" \
  https://app.aurexis.web.id/api/v1/auth/login \
  | grep -i "access-control"
```

Expected response headers:
```
access-control-allow-origin: https://web.aurexis.web.id
access-control-allow-credentials: true
```

---

## Step 3: Frontend Deployment

SSH into `129.225.33.77`:

```bash
cd ~/AUREXIS
git pull origin main
bash scripts/deploy_frontend_vps.sh
```

This script:
1. Installs Node.js dependencies (`npm ci`)
2. Builds Next.js (`npm run build`)
3. Installs systemd service (`aurexis-frontend.service`)
4. Installs Nginx virtual host (`web.aurexis.web.id.conf`)
5. Issues Let's Encrypt SSL certificate via `certbot --nginx`
6. Reloads Nginx

---

## Node.js Requirement

The VPS must have Node.js 22 LTS installed. If not:

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs
node --version  # v22.x
```

---

## Systemd Service

```
aurexis-frontend.service
  WorkingDirectory: /home/ubuntu/AUREXIS/frontend
  ExecStart: npm start (Next.js standalone server on :3000)
  Restart: on-failure
```

Commands:
```bash
sudo systemctl status aurexis-frontend
sudo systemctl restart aurexis-frontend
sudo journalctl -u aurexis-frontend -f
```

---

## Nginx Configuration

File: `/etc/nginx/sites-available/web.aurexis.web.id`

Key settings:
- HTTP → HTTPS redirect
- HTTPS with Let's Encrypt certificate
- Proxy to `127.0.0.1:3000` (Next.js)
- Next.js static files cache headers
- Security headers (X-Frame-Options, CSP, etc.)

```bash
sudo nginx -t
sudo systemctl reload nginx
sudo systemctl status nginx
```

---

## Verification

After deployment, verify end-to-end:

```bash
# DNS
curl -I https://web.aurexis.web.id/

# Backend health
curl -s https://app.aurexis.web.id/api/v1/health | python3 -m json.tool

# CORS preflight
curl -I -X OPTIONS \
  -H "Origin: https://web.aurexis.web.id" \
  -H "Access-Control-Request-Method: POST" \
  https://app.aurexis.web.id/api/v1/auth/login
```

---

## Secrets Required on VPS Backend .env

| Variable | Description |
|---|---|
| `APP_ENV` | `production` |
| `DATABASE_URL` | PostgreSQL URL |
| `REDIS_URL` | Redis URL |
| `JWT_SECRET` | 32+ byte hex secret |
| `ENCRYPTION_KEY` | 32+ byte hex key |
| `MT5_AGENT_SECRET_KEY` | MT5 HMAC secret |
| `CORS_ORIGINS` | `https://web.aurexis.web.id` |

---

## Troubleshooting

### `curl https://web.aurexis.web.id` fails

Check:
1. DNS propagated: `nslookup web.aurexis.web.id 8.8.8.8` returns `129.225.33.77`
2. Certbot succeeded: `ls /etc/letsencrypt/live/web.aurexis.web.id/`
3. Nginx running: `sudo systemctl status nginx`
4. Frontend service running: `sudo systemctl status aurexis-frontend`

### CORS errors in browser

Check `CORS_ORIGINS=https://web.aurexis.web.id` is in `/home/ubuntu/AUREXIS/.env`.
Restart backend: `sudo systemctl restart aurexis-backend`.

### API 401 Unauthorized

Verify:
1. JWT_SECRET is set on backend
2. Token is being sent via `Authorization: Bearer <token>` header
