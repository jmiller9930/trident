# TRIDENT IMPLEMENTATION DIRECTIVE 100A
## Phase 2 Start — Repository + Runtime Skeleton

---

## 1. Purpose

Begin Trident Phase 2 implementation by creating the initial repository structure, runtime service skeleton, container layout, health endpoints, configuration placeholders, and validation proof requirements.

This directive authorizes only the runtime skeleton. It does not authorize implementation of agent logic, memory logic, MCP execution, router behavior, file mutation, Git automation, or UI business logic.

---

## 2. Parent Architecture References

This implementation directive is governed by:

- Trident Foundation v1.1
- Trident Document Manifest v1.0
- Directive 000A — Schemas + Graph Contracts
- Directive 000B — Task Ledger + LangGraph State Machine
- Directive 000J — Deployment + Runtime Architecture
- Directive 000K — Engineering Implementation Plan
- Directive 000L — QA + Validation Framework

---

## 3. Implementation Scope

Engineering must create the initial Trident project skeleton with the following service boundaries:

```text
trident/
  backend/
    app/
      main.py
      api/
      core/
      config/
      health/
      version/
    tests/
  frontend/
    src/
    public/
  worker/
    app/
  exec/
    app/
  docker/
  docs/
  scripts/
  config/
  runtime/
    logs/
    proof/
  docker-compose.yml
  .env.example
  README.md
```

---

## 4. Required Services

The first runtime skeleton must define the following containers/services:

### 4.1 trident-api

Purpose:
- FastAPI backend skeleton
- Health endpoints
- Version endpoint
- Placeholder API namespace

Required endpoints:
- `GET /api/health`
- `GET /api/ready`
- `GET /api/version`

No business logic is allowed yet.

---

### 4.2 trident-web

Purpose:
- Web UI skeleton
- Static placeholder page
- Must prove frontend can run and reach backend health endpoint

No workflow UI is required yet.

---

### 4.3 trident-worker

Purpose:
- Background worker placeholder
- Must start and write heartbeat log

No indexing or memory work is allowed yet.

---

### 4.4 trident-exec

Purpose:
- MCP execution service placeholder
- Must expose health endpoint or heartbeat

No shell/SSH/vCenter execution is allowed yet.

---

### 4.5 trident-db

Purpose:
- PostgreSQL container placeholder
- Persistence volume must be configured

No schema migration is required yet.

---

### 4.6 trident-vector

Purpose:
- ChromaDB or placeholder vector service
- Persistence volume must be configured

No indexing is required yet.

---

## 5. Hard Constraints

Engineering must not:

- Implement agents
- Implement LangGraph workflow
- Implement memory reads/writes
- Implement external API routing
- Implement MCP execution
- Implement Git/file mutations
- Add hidden shell execution
- Add hardcoded secrets
- Use mock proof as acceptance

This directive is skeleton only.

---

## 6. Configuration Requirements

Create `.env.example` with placeholders only:

```text
TRIDENT_ENV=development
TRIDENT_API_HOST=0.0.0.0
TRIDENT_API_PORT=8000
TRIDENT_WEB_PORT=3000
TRIDENT_DB_HOST=trident-db
TRIDENT_DB_PORT=5432
TRIDENT_VECTOR_HOST=trident-vector
TRIDENT_VECTOR_PORT=8001
TRIDENT_LOG_LEVEL=INFO
```

No real secrets may be committed.

---

## 7. Logging Requirements

Each service must write startup logs.

Minimum required log events:

```text
service_start
service_ready
service_health_check
service_shutdown
```

Logs must be visible through Docker logs.

---

## 8. Health Check Requirements

Engineering must implement basic health checks for:

- API process alive
- Web process alive
- Worker process alive
- Exec process alive
- Database container reachable
- Vector container reachable or placeholder health reachable

---

## 9. Validation Commands

Engineering must provide exact commands used to validate the skeleton.

Minimum required commands:

```bash
docker compose build
docker compose up -d
docker compose ps
curl http://localhost:8000/api/health
curl http://localhost:8000/api/ready
curl http://localhost:8000/api/version
docker compose logs --tail=100
docker compose down
docker compose up -d
curl http://localhost:8000/api/health
```

---

## 10. Required Tests

Engineering must create initial tests for:

- API health endpoint
- API readiness endpoint
- API version endpoint
- import safety
- configuration loading

Tests must run with a single command.

Example:

```bash
pytest backend/tests
```

---

## 11. Proof Objects Required

Engineering must return:

```text
1. Git branch name
2. Git commit hash
3. File tree output
4. docker compose build output
5. docker compose ps output
6. health endpoint outputs
7. pytest output
8. restart persistence proof
9. confirmation that no real secrets were committed
```

---

## 12. Acceptance Criteria

Directive 100A is accepted only if:

- Repository skeleton exists
- Required service directories exist
- Docker Compose starts all skeleton services
- API health endpoints return success
- Logs are visible
- Tests pass
- Database and vector persistence volumes are declared
- No unauthorized business logic is implemented
- No secrets are committed
- Git commit exists

---

## 13. Failure Conditions

Reject the implementation if:

- Any service fails to start
- Health endpoints are missing
- Docker Compose is not reproducible
- Secrets are committed
- Business logic is added prematurely
- Any shell/SSH/MCP execution behavior is implemented
- Tests are missing
- No commit hash is provided

---

## 14. Engineering Return Format

Engineering must reply in this format:

```text
Directive: 100A
Status: PASS | FAIL | PARTIAL
Branch:
Commit:
Files Created:
Commands Run:
Test Output:
Proof Objects:
Known Gaps:
Next Recommended Directive:
```

---

## 15. Manifest Link

Parent: Trident Manifest v1.0  
Depends on: 000A–000N  
Phase: 2  
Unlocks: Implementation Directive 100B — Schema + Persistence Foundation

---

END OF DOCUMENT
