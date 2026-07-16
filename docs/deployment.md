# Deployment

## Stack overview

Docker Compose stack defined in `deploy/docker-compose.prod.yml` (included via `compose.yml` at repo root).

Services: `postgres`, `redis`, `aiservice`, `backend`, `celery-worker`, `celery-beat`, `frontend`, `caddy`.

Traffic path: Browser → Nginx Proxy Manager (HTTPS termination) → Caddy (HTTP :80, internal router) → Next.js `frontend:3000`. The backend is internal-only at `backend:8000`.

`DOMAIN` in `.env` is a bare domain (e.g. `DOMAIN=kunde.avisiohub.cloud`). The Caddyfile hardcodes the `http://` scheme, so Caddy never attempts ACME/auto-HTTPS — TLS is NPM's job. Serving TLS from Caddy directly would be an architecture change (edit the Caddyfile), not a config flag.

## How code gets into containers

**All application services bake source code into the Docker image at build time.** There are no code volume mounts. A `docker compose restart` reloads the process but does not pick up file changes — a `--build` is always required.

| What changed | Command |
|---|---|
| Backend Python (`backend/`) | `docker compose up -d --build backend celery-worker celery-beat` |
| Frontend TypeScript (`frontend/`) | `docker compose up -d --build frontend` |
| AI service Python (`aiservice/`) | `docker compose up -d --build aiservice` |
| Caddyfile (`deploy/Caddyfile`) | `docker compose restart caddy` (volume-mounted, no rebuild needed) |
| AI prompts (`aiservice/prompts/`) | No action needed — prompts are read from disk at request time |

## Test server

- **Host:** `YOUR_SERVER_IP` (Debian LXC inside Proxmox)
- **SSH:** `ssh root@YOUR_SERVER_IP`
- **URL:** `https://openavisio.org`
- **Stack location:** `/opt/openavisio/`
- **Env file:** `/opt/openavisio/.env`

### Deploying a change

Always run `docker compose` from `/opt/openavisio/`, not from `deploy/`. Running from `deploy/` creates a separate `deploy-*` project that is not the live stack.

```bash
# 1. Copy changed files to the server
scp backend/app/routers/documents.py root@YOUR_SERVER_IP:/opt/openavisio/backend/app/routers/documents.py

# 2. Rebuild and restart the affected service(s)
ssh root@YOUR_SERVER_IP "cd /opt/openavisio && docker compose up -d --build backend celery-worker celery-beat"
```

For the Caddyfile (no rebuild needed):
```bash
scp deploy/Caddyfile root@YOUR_SERVER_IP:/opt/openavisio/deploy/Caddyfile
ssh root@YOUR_SERVER_IP "cd /opt/openavisio && docker compose restart caddy"
```

### Viewing logs

```bash
# Backend (FastAPI)
ssh root@YOUR_SERVER_IP "docker logs openavisio-backend-1 --tail 100"

# Celery worker
ssh root@YOUR_SERVER_IP "docker logs openavisio-celery-worker-1 --tail 100"

# All services, live
ssh root@YOUR_SERVER_IP "cd /opt/openavisio && docker compose logs -f --tail 50"
```

## Backups

Two layers, per ADR-022:

- **ZFS native encryption** on the Postgres data volume — covers a stolen/decommissioned disk.
- **age-encrypted `pg_dump`** of `vaultdb`, with the age key held **out-of-band** (never inside the backup) — covers backup exfiltration. Keep the `DOCUMENT_ENCRYPTION_KEY` (master KEK) backed up out-of-band too; losing it means permanent loss of all documents.

### Keystore is a SEPARATE, short-retention stream (ADR-031)

Per-patient KEKs live in the **`patient_keys`** table. Crypto-shredding (erasing one
patient deletes their KEK, rendering their encrypted documents/text unrecoverable)
only reaches **backups** if the KEK is not restorable from a backup. So `patient_keys`
must be backed up **apart from the rest of `vaultdb`, with short retention** (days),
while the clinical data keeps its normal long retention.

Practical recipe — two dump streams instead of one:

```bash
# 1. Main clinical dump, EXCLUDING the keystore — long retention (e.g. 90 days)
pg_dump -U openavisio --exclude-table=patient_keys vaultdb \
  | age -r "$AGE_PUBKEY" > clinical-$(date +%F).sql.age

# 2. Keystore-only dump — SHORT retention (e.g. 7 days), pruned aggressively
pg_dump -U openavisio --table=patient_keys vaultdb \
  | age -r "$AGE_PUBKEY" > keystore-$(date +%F).sql.age
```

After a patient is erased, their KEK is gone from live data immediately and drops out
of every keystore backup once the 7-day window rolls — at which point the clinical
backups still holding their ciphertext become permanently undecryptable. **A restore
needs both streams for the same date** to bring documents back online.

If you skip the split (one combined dump), crypto-shredding still isolates blast radius
and shreds **live** data, but no longer reaches old backups — it degrades cleanly to the
ADR-022 guarantee. Nothing breaks; the erasure claim just narrows.
