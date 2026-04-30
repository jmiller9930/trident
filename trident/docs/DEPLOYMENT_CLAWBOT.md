# Deployment target — clawbot.a51.corp /trident

Trident runtime (100A+) is built to run **Dockerized** behind a reverse proxy path:

| Setting | Example |
|---------|---------|
| Public URL | `https://clawbot.a51.corp/trident` (or `http://…` until TLS is ready) |
| Path prefix | `/trident` (`TRIDENT_BASE_PATH`) |

## Reverse proxy expectation

The edge proxy should route `https://clawbot.a51.corp/trident/` to `trident-web` and `…/trident/api/` (and downstream paths) to `trident-api`, **or** strip `/trident` and forward to backends according to your ingress rules. The API serves routes under **`${TRIDENT_BASE_PATH}/api/*`** when `TRIDENT_BASE_PATH` is set (e.g. `/trident/api/health`).

## Prerequisites checklist (verify on clawbot **before** deploy)

Stop and report if any required item is missing or unresolved.

- [ ] DNS resolves: `clawbot.a51.corp`
- [ ] SSH access to clawbot
- [ ] Docker installed and daemon running
- [ ] Docker Compose available (`docker compose version`)
- [ ] Git installed (for checkout/pull)
- [ ] Repo checkout location agreed (path on disk)
- [ ] Persistent storage path selected for Docker volumes (Postgres / proof paths)
- [ ] Ports or upstream proxy slots available for mapped services (and `/trident` path on proxy)
- [ ] Firewall allows required inbound access (HTTPS/HTTP as planned)
- [ ] TLS / reverse-proxy placement understood (who terminates TLS)
- [ ] Service account / permissions for Docker and data dirs confirmed
- [ ] Backup path or policy available for DB volume

## Configuration

Copy `.env.example` to `.env` and set at minimum:

```text
TRIDENT_PUBLIC_BASE_URL=https://clawbot.a51.corp/trident
TRIDENT_BASE_PATH=/trident
TRIDENT_ENV=development
```

Adjust `TRIDENT_PUBLIC_BASE_URL` if you only use HTTP initially.

## 100A proof on clawbot

Operator-run bundle (logs + curls + restart): from `trident/` after deploy,

```bash
bash scripts/clawbot-proof-bundle.sh
```

With prerequisites satisfied:

1. `docker compose build && docker compose up -d`
2. From clawbot (or via SSH): `curl -fsS https://clawbot.a51.corp/trident/api/health` (or `http://…`) — expect JSON `{"status":"ok",…}`
3. Open `https://clawbot.a51.corp/trident/` — static page should show API health via configured URL
4. `docker compose logs` — startup lines include `service_start` / `service_ready`
5. `docker compose restart trident-api` — health still OK (restart persistence)
6. Confirm `.env` with secrets is **not** committed (only `.env.example` in git)

## Git alignment (100A final — required)

Deployments must follow:

```text
local → commit → push → clawbot → pull → run → prove
```

**No exceptions.**

### Checkout layout on clawbot

After `git clone <REMOTE_URL> trident` under `~/code_projects/trident`, the **repository root** is `~/code_projects/trident/trident`. Compose and runtime live **one level deeper**:

```text
~/code_projects/trident/trident/trident/docker-compose.yml
```

Deploy from that directory (not the repo root):

```bash
cd ~/code_projects/trident/trident/trident
cp .env.example .env   # configure TRIDENT_* first if needed
docker compose up -d --build
```

### Initial alignment (if the tree was copied without `.git`)

```bash
cd ~/code_projects/trident/trident && docker compose down 2>/dev/null || true
cd ~/code_projects/trident && rm -rf trident
git clone <REMOTE_URL> trident
cd trident
git checkout main
git pull origin main
git rev-parse HEAD
cd trident
cp .env.example .env
docker compose down 2>/dev/null || true
docker compose up -d --build
```

Replace `<REMOTE_URL>` with your canonical **origin** (same remote used from developer laptops).

## Database migrations (100B)

The API image entrypoint runs **`python -m alembic upgrade head`** before `uvicorn`, so tables are applied on container start.

Equivalent manual commands (from the compose directory where `docker-compose.yml` lives):

```bash
docker compose exec trident-api python -m alembic upgrade head
docker compose exec trident-api python -m alembic downgrade -1   # rollback one revision
# Tests run on the host checkout (API image does not ship tests):
# cd backend && PYTHONPATH=. pytest -q
```

Clean DB volume (destructive): `docker compose down -v` then bring the stack back up.

## Stop condition

If clawbot lacks Docker, Compose, DNS, persistent storage, or a viable reverse-proxy path for `/trident`, **stop** and report gaps **before** relying on this deployment path.
