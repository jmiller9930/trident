# Trident — runtime skeleton (100A)

Phase 2 implementation skeleton only: API, web placeholder, worker heartbeat, exec placeholder, Postgres, vector placeholder. No LangGraph, MCP product logic, agents, memory, router, or Git automation.

## Prerequisites

- Docker / Docker Compose v2
- Python 3.12+ (for local pytest without containers)

## Quick start

From this directory (`trident/`):

```bash
cp .env.example .env
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

Web UI (static page calling API from the browser): open `http://localhost:3000`.

## Tests (single command)

```bash
cd backend && python -m pytest
```

Or with venv: create `.venv`, install `backend/requirements.txt`, then `cd backend && pytest`.

## Services

| Service | Role |
|---------|------|
| trident-api | FastAPI — `/api/health`, `/api/ready`, `/api/version` |
| trident-web | nginx — static placeholder |
| trident-worker | Heartbeat logs only |
| trident-exec | Placeholder HTTP `/health` on port 8010 |
| trident-db | PostgreSQL 16 |
| trident-vector | Minimal FastAPI `/health` placeholder (not production vector DB) |

## Documentation cleanup

See `docs/DOCUMENTATION_CLEANUP_LOG.md` (e.g. Foundation v1.1 file tracking).
