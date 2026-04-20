# EC2 Deployment — Ubuntu

Target: Ubuntu 22.04+ on Amazon EC2. The service runs as an in-process FastAPI +
APScheduler under systemd, fronted by nginx.

## 1. System packages

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip nginx git
```

## 2. Lay out the code

```bash
sudo mkdir -p /opt/newsagg
sudo chown "$USER":"$USER" /opt/newsagg
# Upload / clone repo into /opt/newsagg. Example with rsync from your laptop:
#   rsync -av --exclude .venv --exclude data --exclude __pycache__ ./ ec2:/opt/newsagg/
cd /opt/newsagg
mkdir -p data logs public
```

## 3. Python env

```bash
cd /opt/newsagg
python3.11 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

## 4. Config

```bash
cp .env.example .env
# Edit .env as needed. Keep HOST=127.0.0.1 — nginx fronts it.
```

## 5. Initialize the DB (idempotent)

```bash
.venv/bin/python -m app.db.init
```

## 6. systemd service

```bash
sudo cp deploy/newsagg.service /etc/systemd/system/newsagg.service
sudo systemctl daemon-reload
sudo systemctl enable --now newsagg
sudo systemctl status newsagg --no-pager
# Logs:
sudo journalctl -u newsagg -f
```

Smoke test locally on the box:

```bash
curl -s http://127.0.0.1:8000/api/health
curl -s http://127.0.0.1:8000/api/snapshot | head -c 500
```

## 7. nginx

```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/newsagg
sudo ln -sf /etc/nginx/sites-available/newsagg /etc/nginx/sites-enabled/newsagg
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

## 8. Security group

Inbound on the EC2 security group:
- **80 (HTTP)** from `0.0.0.0/0` for now
- **22 (SSH)** locked to your IP
- Add **443 (HTTPS)** once TLS is set up (see step 10)

Do **not** expose port 8000 publicly — uvicorn binds to 127.0.0.1, and nginx is
the only thing that talks to it.

## 9. Verify from outside

```bash
curl http://<ec2-public-ip>/api/health
curl http://<ec2-public-ip>/api/snapshot | jq '.major_news | length'
```

Wait ~60 seconds after service start for the first ingest to populate.

## 10. TLS (when you have a domain)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
# Auto-renew is installed by certbot.
```

Then update `server_name` in `deploy/nginx.conf` to match the domain.

## 11. Cloudflare Tunnel (for os.joshphoenix.com)

Cloudflare Tunnel exposes the EC2 origin to the public internet without opening
inbound ports. TLS is terminated at the Cloudflare edge — nginx-level certbot
is not needed if the tunnel is in front.

### 11a. Install cloudflared on Ubuntu

```bash
curl -L -o /tmp/cloudflared.deb \
  https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i /tmp/cloudflared.deb
cloudflared --version
```

### 11b. Get the connector token

In the Cloudflare Zero Trust dashboard:
- **Networks → Tunnels →** your tunnel **→ Configure → Connectors → Install connector**
- Pick **Debian / Ubuntu 64-bit**
- Copy the `cloudflared service install <TOKEN>` line — the TOKEN is a long
  base64/JWT string starting with `eyJ...`.

Under **Public Hostname** of the same tunnel, add:
- **Subdomain:** `os`  ·  **Domain:** `joshphoenix.com`
- **Service:** `HTTP`  ·  **URL:** `localhost:8000`

### 11c. Install the service (token stays outside git)

```bash
# Paste the install command the dashboard gave you. The TOKEN ends up in
# /etc/systemd/system/cloudflared.service and is NEVER in this repo.
sudo cloudflared service install <TOKEN>
sudo systemctl enable --now cloudflared
sudo systemctl status cloudflared --no-pager
```

Verify the tunnel is up:

```bash
sudo journalctl -u cloudflared -f    # should see "Registered tunnel connection" 4×
curl -sI https://os.joshphoenix.com/api/health   # expect HTTP/2 200
```

### 11d. CORS / nginx interaction

Nginx is no longer strictly required with the tunnel in front — cloudflared
talks directly to `localhost:8000`. Either:
- Keep nginx for future same-origin static serving (tunnel → nginx → uvicorn), or
- Point cloudflared directly at the uvicorn port and disable the nginx site.

The API sets `Access-Control-Allow-Origin: *` already, so cross-origin calls
from Cloudflare Pages (if you later move the frontend there) also work.

### 11e. Rotating or replacing the token

```bash
sudo cloudflared service uninstall
sudo cloudflared service install <NEW_TOKEN>
sudo systemctl enable --now cloudflared
```

## Operational notes

- **Logs:** `journalctl -u newsagg -f` for app, `/var/log/nginx/newsagg.*.log` for http.
- **Restart after code change:** `sudo systemctl restart newsagg`.
- **DB location:** `/opt/newsagg/data/news.db` (SQLite WAL mode). Back up with a
  simple `sqlite3 news.db ".backup '/path/to/backup.db'"` on a cron if desired.
- **Retention:** articles >72h are pruned daily; override via `ARTICLE_RETENTION_HOURS`.
- **Missing Gulf indices:** `^ADI`, `^DFMGI`, `^QSI`, `^TASI.SR` are best-effort on
  Yahoo — if a ticker stops resolving, the fetcher logs it to `fetch_log` and
  continues. Swap the symbol in `app/config.py` if a better one is found.
