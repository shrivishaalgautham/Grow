# Grow — simple, Portainer-managed deploy

Same ideology as `gtm_solutions/infrastructure`'s `docs/simple-portainer-deploy.md`
(applied to finance_analyzer and internal_kanban), scoped to Grow's single
app on its own Ubuntu VM. **One container per service.** A deploy is "stop
it, pull the new image, start it again" — Portainer already does exactly
that out of the box, so nothing extra needs to be built:

- No auto-deploy trigger of any kind. Your app repos' CI (if any) can build
  and push an image to Docker Hub and stop there; nothing here pulls
  automatically.
- No SSH keys, no GitHub Actions wiring, no `deploy.sh`.
- Redeploy = open the `grow` stack in Portainer, bump an image tag in its
  **Environment variables** panel, click **Update the stack** with
  **Re-pull image** checked.
- Downtime on every deploy is accepted (however long pull + start +
  migrate takes — typically seconds). If that stops being acceptable, look
  at blue/green (two colors + a health-gated cutover script) instead —
  deliberately not built here.

## What's in this app

- **Backend** (`watchlist/backend`) — FastAPI + uv, Postgres, optional
  Redis (falls back to an in-process cache if unreachable — see
  `app/cache.py`). Runs its own background scheduler in-process
  (`app/jobs/scheduler.py`, started from `main.py`'s lifespan) — no
  separate worker container needed. Boot-time `alembic upgrade head` runs
  on every container start (see its `Dockerfile`'s `CMD`), same as local
  dev — there's no idle color to protect from a bad migration, so a bad
  migration just takes this one container down until you fix and redeploy.
- **UI** (`ui`) — Next.js, `output: "standalone"`. All backend routes are
  mounted under `/api/` (see `watchlist/backend/app/main.py`), so nginx
  routes by **path**, not by subdomain: one domain, `/api/` to the
  backend, everything else to the UI. Same-origin — no CORS preflight for
  the browser's own calls.

## Networking and nginx

Two Docker networks, created once, external to every stack:

- `grow-data` — Postgres, Redis, backend. Nothing else reaches it.
- `grow-edge` — backend, ui, nginx. Nginx is the only thing on `grow-edge`
  that's also reachable from outside the VM (port 80/443).

`nginx/conf.d/grow.conf` is a static, checked-in server block. What it
proxies to lives in `nginx/active/*.conf` (gitignored — see
`.gitignore`), seeded once from the committed `.example` files and never
rewritten again, since there's only ever one backend/ui container:

```
set $grow_backend "http://grow-backend:8000";
set $grow_ui      "http://grow-ui:3000";
```

Keep the `resolver 127.0.0.11` + variable pattern (already in
`conf.d/grow.conf`) even though nothing ever rewrites these files again —
it's what lets nginx start before `grow-backend`/`grow-ui` exist, and ride
through the container-recreate window during a redeploy (briefly 502ing
rather than refusing to start or caching a dead IP).

## The `automation` user

Ordinary login shell, `docker` group, not a forced-command account —
there's no `deploy.sh` to restrict here; deploys happen by clicking around
in Portainer's own UI, authenticated by Portainer's own login. `ssh
automation@<vm>` for one-off commands (seed networks, `docker ps`, restore
a backup). **`docker` group membership is root-equivalent** — socket
access is arbitrary code execution as root, regardless of what the account
is named or how narrowly you intend to use it. Portainer itself needs the
same access to manage containers at all.

## Runbook

### 1. Provision the VM

```bash
git clone <this repo's URL> ~/grow   # or wherever you keep it
cd ~/grow/infra
./bootstrap.sh
```

Installs Docker Engine + Compose, git, curl, and creates the `automation`
user — nothing else. This VM never builds from source, so no `uv`/Node/pnpm
are installed (contrast `gtm_solutions/infrastructure/bootstrap.sh`, which
supports a local-dev workflow too; this one is a pure deploy target).

### 2. Create the two networks (once)

```bash
docker network create grow-data
docker network create grow-edge
```

### 3. Bring up Postgres + Redis

```bash
cd stacks/postgres-redis
cp .env.example .env   # fill in a real POSTGRES_PASSWORD
docker compose up -d
```

### 4. Seed nginx's upstream pointers, then bring nginx up

```bash
cd ../../nginx
mkdir -p active
for f in active/*.example; do cp "$f" "active/$(basename "$f" .example)"; done
docker compose up -d
```

Safe to start before `grow-backend`/`grow-ui` exist — nginx just 502s
until something answers. What it can't tolerate is the `active/*.conf`
*file* being absent (the `include` directive fails at config-parse time),
so these two files must exist, with these plain names, before nginx
starts.

### 5. Bring up Portainer

```bash
cd ../stacks/portainer
docker compose up -d
```

Reach it over an SSH tunnel — never expose it publicly:

```bash
ssh -L 9443:127.0.0.1:9443 automation@<vm>
```
then open `https://localhost:9443` and finish Portainer's first-run setup
(create the admin account).

### 6. Build and push the images

This VM never builds anything. `.github/workflows/docker-publish.yml`
builds and pushes both images to Docker Hub automatically on every push
to `main` that touches `watchlist/backend/` or `ui/` (needs the repo's
`DOCKERHUB_USERNAME`/`DOCKERHUB_TOKEN` secrets, and `NEXT_PUBLIC_API_MODE`/
`NEXT_PUBLIC_API_BASE_URL` repo variables set to `live` and this app's
real domain — see that workflow file) — that's the normal path.

To build and push manually instead:

```bash
cd watchlist/backend
docker build -t <dockerhub-user>/smart-market-watchlist-backend:sha-$(git rev-parse HEAD) .
docker push <dockerhub-user>/smart-market-watchlist-backend:sha-$(git rev-parse HEAD)
```

**The UI image is different — two build-args are baked in at build time,
not set later at runtime:**

```bash
cd ui
docker build \
  --build-arg NEXT_PUBLIC_API_MODE=live \
  --build-arg NEXT_PUBLIC_API_BASE_URL=https://kaaviya-groww-hackathon.duckdns.org \
  -t <dockerhub-user>/smart-market-watchlist-frontend:sha-$(git rev-parse HEAD) .
docker push <dockerhub-user>/smart-market-watchlist-frontend:sha-$(git rev-parse HEAD)
```

Miss `NEXT_PUBLIC_API_MODE=live` and the UI silently ships in **fixture
mode** — it serves canned demo data and never calls your real backend at
all (see `ui/src/api/client.ts`). Miss the real domain in
`NEXT_PUBLIC_API_BASE_URL` and it calls `http://localhost:8000` from every
visitor's browser instead. Both defaults come from `ui/Dockerfile`'s `ARG`
lines — there is no way to fix either after the fact except rebuilding and
re-pushing the image; Portainer's environment-variable panel cannot change
something baked into a static Next.js build.

### 7. Create the `grow` stack in Portainer

**Stacks → Add stack**, name `grow`, pointing at
`infra/stacks/grow/docker-compose.yml` (paste the file's content, or use
Portainer's "Repository" method against this repo, path `infra/stacks/grow`).

In the stack's **Environment variables** panel (not a file — this is what
you edit to redeploy):
```
DOCKERHUB_USER=<your Docker Hub user/org>
BACKEND_IMAGE_TAG=sha-<40 hex chars, or "latest">
UI_IMAGE_TAG=sha-<40 hex chars, or "latest">
```

Copy `stacks/grow/.env.example` to a real `stacks/grow/.env` on the VM
first — it holds the app's actual runtime config/secrets (DB URL,
OpenRouter/Google API keys, SMTP, OIDC) and is read via `env_file:`,
separate from the tag variables above. `ALLOWED_ORIGINS`/`APP_BASE_URL`/
`API_BASE_URL`/`OIDC_REDIRECT_URI` are already set to
`kaaviya-groww-hackathon.duckdns.org` — Google rejects a raw-IP redirect
URI outright, so this domain (see step 9) is required for Google sign-in
to work at all, not optional. The OIDC redirect URI must exactly match
what's registered for this client in the Google OAuth console.

Deploy the stack, then verify:
```bash
docker ps --format '{{.Names}}: {{.Status}}'
curl -I http://127.0.0.1:8001/api/health   # backend
curl -I http://127.0.0.1:8011              # ui
```

### 8. Redeploying

New image pushed to Docker Hub (rebuild per step 6 — remember the UI's
build-args if anything about the domain or API mode changed). Then, in
Portainer:

1. Open the `grow` stack.
2. Edit **Environment variables**: set `BACKEND_IMAGE_TAG` and/or
   `UI_IMAGE_TAG` to the new tag (or leave both as `latest` permanently, if
   you'd rather not copy tags by hand).
3. **Update the stack**, with **"Re-pull image"** checked.

Whatever's serving on `grow-backend`/`grow-ui` is briefly gone during that
window — nginx 502s until the new container's healthcheck passes — then
traffic resumes. No nginx step needed; `active/*.conf` never changes
because the container names never change.

### 9. Domain, DNS, and HTTPS

No purchased domain here — Google's OAuth console rejects a raw-IP
redirect URI outright (separate rule from the HTTP-vs-HTTPS one, so even
`https://<ip>/...` fails), so Google sign-in requires a real registrable
hostname. `kaaviya-groww-hackathon.duckdns.org` (free, via
[duckdns.org](https://www.duckdns.org)) is that hostname, pointed at this
VM's public IP `20.6.33.140`. `nginx/conf.d/grow.conf` and
`stacks/grow/.env` are already set to this domain.

1. Verify DNS actually resolves to this VM before continuing:
   ```bash
   dig +short kaaviya-groww-hackathon.duckdns.org
   ```
   Must print `20.6.33.140`. If it doesn't, fix the IP on DuckDNS's site
   for this domain and re-check — nothing past this step works until it
   matches.
2. Open the firewall: `sudo ufw allow 80/tcp && sudo ufw allow 443/tcp`
   (skip if `ufw` isn't active on this VM — check `sudo ufw status` first).
3. Issue the certificate with certbot (webroot method — no downtime, nginx
   keeps running). This needs nginx already up (step 4) with the
   acme-challenge location in place:
   ```bash
   cd nginx
   mkdir -p certbot/www certbot/conf
   docker run --rm \
     -v "$(pwd)/certbot/www:/var/www/certbot" \
     -v "$(pwd)/certbot/conf:/etc/letsencrypt" \
     certbot/certbot certonly --webroot -w /var/www/certbot \
     -d kaaviya-groww-hackathon.duckdns.org \
     --email you@example.com --agree-tos --no-eff-email
   ```
4. Switch to HTTPS: in `nginx/conf.d/grow.conf`, replace the plain-HTTP
   proxying `location /` block with a redirect (keep the acme-challenge
   location) and add a `listen 443 ssl` server block:

   ```nginx
   server {
       listen 80;
       server_name kaaviya-groww-hackathon.duckdns.org;
       location /.well-known/acme-challenge/ { root /var/www/certbot; }
       location / { return 301 https://$host$request_uri; }
   }

   server {
       listen 443 ssl;
       server_name kaaviya-groww-hackathon.duckdns.org;
       ssl_certificate     /etc/nginx/certs/live/kaaviya-groww-hackathon.duckdns.org/fullchain.pem;
       ssl_certificate_key /etc/nginx/certs/live/kaaviya-groww-hackathon.duckdns.org/privkey.pem;
       resolver 127.0.0.11 valid=10s ipv6=off;
       proxy_set_header Host $host;
       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       proxy_set_header X-Forwarded-Proto https;
       location /api/ { include /etc/nginx/active/grow-backend.conf; proxy_pass $grow_backend; }
       location /     { include /etc/nginx/active/grow-ui.conf; proxy_pass $grow_ui; }
   }
   ```

   Then add a `"443:443"` line under `nginx/docker-compose.yml`'s `ports:`.
   Validate before touching the running container:
   ```bash
   cd nginx
   docker run --rm \
     -v "$(pwd)/conf.d:/etc/nginx/conf.d:ro" \
     -v "$(pwd)/active:/etc/nginx/active:ro" \
     -v "$(pwd)/certbot/conf:/etc/nginx/certs:ro" \
     -v "$(pwd)/certbot/www:/var/www/certbot:ro" \
     nginx:1.27-alpine nginx -t
   ```
   Then recreate nginx to pick up the new port (`nginx -s reload` alone
   can't add a published port):
   ```bash
   docker compose up -d
   ```
6. Verify: `curl -I https://kaaviya-groww-hackathon.duckdns.org` and
   `curl -I https://kaaviya-groww-hackathon.duckdns.org/api/health`.
7. Automate renewal — root crontab entry, only reloads nginx if something
   actually renewed:
   ```cron
   0 3 * * * docker run --rm -v /home/automation/grow/infra/nginx/certbot/www:/var/www/certbot -v /home/automation/grow/infra/nginx/certbot/conf:/etc/letsencrypt certbot/certbot renew --webroot -w /var/www/certbot --quiet --deploy-hook "docker exec grow-nginx nginx -s reload"
   ```
   Adjust the path to wherever you actually cloned the repo.

## Rollback

No automatic old-color fallback — that's the whole tradeoff of this
design. Put the previous known-good tag back into
`BACKEND_IMAGE_TAG`/`UI_IMAGE_TAG` and update the stack again. Same
downtime as a forward deploy.

## Backups

Nothing here backs up Postgres automatically. Put a scheduled backup on
the VM:

```bash
sudo crontab -e
```
```cron
0 2 * * * docker exec grow-postgres pg_dumpall -U watchlist | gzip > /opt/grow-backups/$(date +\%Y\%m\%dT\%H\%M\%S).sql.gz
```
Adjust the path and the Postgres user to match `stacks/postgres-redis/.env`.

## What this deliberately does NOT do

- No automated deploy trigger — you build, push, and click "Update the
  stack" in Portainer yourself.
- No health-gated cutover — Portainer's "Re-pull image" doesn't check
  whether the new container came up healthy before nginx routes to it
  again; it just recreates and moves on. Watch for a 502 or `unhealthy` in
  Portainer, then roll back manually if the new image is broken.
- No per-repo GitHub Actions wiring, no SSH deploy keys.
- No automatic pre-migration backup — see "Backups" above.
- No worker/scheduler container — the backend's scheduler runs in-process,
  so exactly one backend replica must ever run at a time (this design
  already guarantees that — there's only ever one container).

## A note on the data provider (from the app's own README)

The backend's Yahoo Finance access is a `User-Agent`/TLS-impersonation
workaround around an access-control restriction, not a licensed feed —
see `../README.md`'s "Rejected" and licensing notes. That's a product
decision, not an infra one, but it means "deployed" here should mean
"reachable by you," not "opened up to the public internet as a real
product" until that's actually resolved.
