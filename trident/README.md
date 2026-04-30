# Trident — runtime skeleton (100A)

Phase 2 implementation skeleton only: API, web placeholder, worker heartbeat, exec placeholder, Postgres, vector placeholder. No LangGraph, MCP product logic, agents, memory, router, or Git automation.

## Deployment target (locked)

Production-style hosting: **Docker on clawbot** under path `/trident`:

- See **`docs/DEPLOYMENT_CLAWBOT.md`** for prerequisite checklist (DNS, SSH, Docker, Compose, proxy, storage, TLS plan).
- Configure via **`TRIDENT_PUBLIC_BASE_URL`** and **`TRIDENT_BASE_PATH`** (see `.env.example`).

Default **local** compose uses empty `TRIDENT_BASE_PATH` (API at `/api/*`). For clawbot-style routing set `TRIDENT_BASE_PATH=/trident` so API serves **`/trident/api/health`**, etc.

## Prerequisites

- Docker / Docker Compose v2
- Python 3.12+ (for local pytest without containers)

## Quick start (local, default paths)

From this directory (`trident/`):

```bash
cp .env.example .env
# For local dev, either leave TRIDENT_BASE_PATH empty or comment clawbot lines in .env
docker compose build
docker compose up -d
docker compose ps
curl -s http://localhost:8000/api/health
curl -s http://localhost:8000/api/ready
curl -s http://localhost:8000/api/version
docker compose logs --tail=100
docker compose down
docker compose up -d
curl -s http://localhost:8000/api/health
```

### Quick start (compose with `/trident` prefix — proxy-style)

In `.env`, **public URL must include the path prefix** so the browser hits the API container:

```text
TRIDENT_BASE_PATH=/trident
TRIDENT_PUBLIC_BASE_URL=http://localhost:8000/trident
```

Then:

```bash
docker compose up -d --build
curl -s http://localhost:8000/trident/api/health
```

Web UI: open `http://localhost:3000` — JS uses `TRIDENT_PUBLIC_BASE_URL` when set, else same-origin + base path.

## Tests (single command)

```bash
cd backend && python -m pytest
```

Or with venv: create `.venv`, install `backend/requirements.txt`, then `cd backend && pytest`.

## Services

| Service | Role |
|---------|------|
| trident-api | FastAPI — health/ready/version under `${TRIDENT_BASE_PATH}/api/...` (default `/api/...`) |
| trident-web | nginx — static placeholder + generated `config.js` |
| trident-worker | Heartbeat logs only |
| trident-exec | Placeholder HTTP `/health` on port 8010 |
| trident-db | PostgreSQL 16 |
| trident-vector | Minimal FastAPI `/health` placeholder (not production vector DB) |

## Documentation cleanup

See `docs/DOCUMENTATION_CLEANUP_LOG.md` (e.g. Foundation v1.1 file tracking).
