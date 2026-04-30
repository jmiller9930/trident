# Trident operations runbook (100L)

Operations reference for `trident/docker-compose.yml`. **Do not** use destructive volume removal on production data without a verified backup.

---

## 1. Service roles & environment

| Service | Role | Key env vars |
|---------|------|----------------|
| **trident-db** | Postgres | `POSTGRES_*` |
| **trident-chroma** | Vector store | `ANONYMOUS_TELEMETRY` (compose sets false) |
| **trident-api** | FastAPI control plane | `TRIDENT_DB_*`, `TRIDENT_CHROMA_*`, `TRIDENT_LOG_LEVEL`, `TRIDENT_BASE_PATH`, `TRIDENT_PUBLIC_BASE_URL` |
| **trident-worker** | Nike dispatcher loop | Same DB vars + `TRIDENT_NIKE_POLL_SEC`, `TRIDENT_NIKE_MAX_ATTEMPTS`, `TRIDENT_NIKE_RETRY_BACKOFF_SEC` |
| **trident-exec** | MCP broker | (service-local config) |
| **trident-web** | Static UI + config template | `TRIDENT_BASE_PATH`, `TRIDENT_PUBLIC_BASE_URL` |

**Secrets:** Never log full connection strings or passwords. Use env files or orchestrator secrets; rotate default `changeme_local_only` before any shared deployment.

**Health URL:** If `TRIDENT_BASE_PATH=/trident`, health is `http://<host>:8000/trident/api/health` (not bare `/api/health`).

---

## 2. Startup order (depends_on)

1. **trident-db** healthy → **trident-chroma** healthy  
2. **trident-api** starts (runs `alembic upgrade head`, then uvicorn)  
3. **trident-web**, **trident-worker**, **trident-exec** wait for **trident-api** **healthy** (worker/exec gated after API passes Dockerfile healthcheck).

---

## 3. Restart & minimal downtime

**Minimal API-only restart (DB + Chroma stable):**

```bash
cd trident
docker compose restart trident-api
# Wait for healthy, then optionally:
docker compose restart trident-worker
```

**Full stack (maintenance window):**

```bash
docker compose down
docker compose up -d
```

**Never** use `docker compose down -v` in normal operations — it deletes named volumes (`trident_db_data`, `trident_chroma_data`).

---

## 4. Failure matrix (expected behavior)

| Condition | Expected |
|-----------|-----------|
| **Postgres down** at startup | API/worker exit or fail healthcheck after migrations; fix DB then `compose up`. |
| **Postgres lost** while API running | Requests/session errors; logs show DB exceptions; restore DB or restart API after DB recovery. |
| **Chroma down** at startup | **trident-api** does not start (compose waits for chroma healthy). |
| **Chroma lost** after startup | Memory vector path may error or mark vector state failed per existing memory semantics; structured DB memory remains authoritative per FIX 004 design — verify logs for `memory_vector` / Chroma client errors. |
| **Nike retry exhaustion** | Dispatcher logs `event=nike_retry_exhausted`; event moves to dead-letter path; bounded by `TRIDENT_NIKE_MAX_ATTEMPTS` (default 5). Outer worker loop sleeps `TRIDENT_NIKE_POLL_SEC` when idle — no tight spin. |

---

## 5. Logs

- **API/worker:** `TRIDENT_LOG_LEVEL` (default `INFO`). Third-party `chromadb`, `httpx`, `httpcore` loggers are capped at WARNING when root is INFO (100L).
- **Follow logs:** `docker compose logs -f trident-api trident-worker`

---

## 6. Read-only audit queries (Postgres)

From host (adjust user/db):

```bash
docker compose exec -T trident-db psql -U trident -d trident -c \
  "SELECT id, event_type, created_at FROM audit_events ORDER BY created_at DESC LIMIT 50;"
```

Use read-only roles in production where possible.

---

## 7. Backup (PostgreSQL)

**Logical backup (recommended):**

```bash
docker compose exec -T trident-db pg_dump -U trident -d trident -Fc -f /tmp/trident.dump
docker compose cp trident-db:/tmp/trident.dump ./backups/trident-$(date +%Y%m%d-%H%M).dump
```

Store dumps off-host. **Chroma:** copy volume or use vendor backup; vector store can be rebuilt from structured memory depending on policy.

---

## 8. Restore (PostgreSQL, testable on staging)

1. Stop writers: `docker compose stop trident-worker trident-api`  
2. Restore DB (example — destructive to DB contents; run only with intent):

```bash
docker compose start trident-db
sleep 5
docker compose cp ./backups/trident-YYYYMMDD.dump trident-db:/tmp/restore.dump
docker compose exec -T trident-db pg_restore -U trident -d trident --clean --if-exists /tmp/restore.dump
```

3. `docker compose up -d` and verify `alembic current` + health + spot-check counts.

Adjust flags (`--clean`) per your retention policy; practice on a copy first.

---

## 9. Resource limits (compose)

Services define `restart: unless-stopped`, `cpus`, and `mem_limit`. Increase **trident-chroma** / **trident-api** if ONNX/embeddings OOM; decrease on constrained hosts.

---

END
