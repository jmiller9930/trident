# TRIDENT IMPLEMENTATION DIRECTIVE 100L
## Production Readiness & Operational Hardening

```yaml
manifest_id: TRIDENT-MANIFEST-v1.0
project: Project Trident
parent_document: TRIDENT_DOCUMENT_MANIFEST_v1_0.md
document_id: TRIDENT-IMPLEMENTATION-DIRECTIVE-100L-PRODUCTION-HARDENING
document_type: Directive
sequence: 100L
status: Issued
dependencies:
  - TRIDENT_IMPLEMENTATION_DIRECTIVE_100J_DEPLOYMENT_PRODUCTION_VALIDATION.md
  - TRIDENT_MASTER_EXECUTION_GUIDE_v1_1.md
produces:
  - Hardened compose / runbook / logging configuration (no new product features)
langgraph_required: true
```

---

## 1. Purpose

Harden Trident for **stable operation**: deployment resilience, bounded failure behavior, observability, security hygiene, data safety, and operator runbooks.

This directive is **hardening and documentation only**. It does not add product features or change the architectural spine (LangGraph, **100G** router, MCP, agents, Nike).

---

## 2. Scope

**In scope**

- **Deployment stability:** container restart policies; CPU/memory resource limits in Compose (as supported by the target runtime); `depends_on` + healthcheck ordering reviewed and documented.
- **Failure handling:** DB unavailable / degraded behavior (API, worker); Chroma unavailable vs structured memory fallback (per existing **FIX 004** semantics); Nike worker retry bounds and DLQ behavior **documented and verified** (env + code paths), no unbounded hot loops.
- **Observability:** log level policy; reduction of third-party **debug** noise where safe; `audit_events` query access for operators; actionable error/correlation logging on critical paths.
- **Security baseline:** no secrets in logs; environment variable scoping by service; **no** new execution surfaces outside MCP.
- **Data safety:** backup procedure (e.g. `pg_dump` or volume snapshot); restore procedure; runbook **without** destructive defaults (`down -v`, etc.) in normal operations.
- **Operational runbook:** safe single-service vs full-stack restart; minimal-downtime path; known-good recovery order (DB → migrations → API → worker → health checks, respecting **`TRIDENT_BASE_PATH`** where applicable).

**Out of scope**

- New features, API contracts, graph nodes, router/MCP/agent behavior changes.
- **100R** model routing.
- Web UI or IDE work (see **100U** / **100K** / **100P**–**100N**).

---

## 3. Core Principle

> Reliability and operability are proven by **configuration, documentation, and validation** — not by expanding the product surface.

---

## 4. Hard Constraints

Engineering must **NOT**:

- add features or user-visible behavior beyond hardening
- change LangGraph, **100G** router, MCP execution semantics, or agent layer contracts
- implement model routing (**100R**)
- introduce new tool/execution paths outside existing MCP governance

---

## 5. Acceptance Criteria

- Compose (and/or override files) reflect agreed restart and resource policies where applicable.
- Documented behavior for DB down / Chroma down / worker retry exhaustion matches observations on a real stack (e.g. clawbot or equivalent).
- Log policy documented; production default avoids debug spam; errors remain diagnosable.
- Operator can run documented **`audit_events`** (and related) read-only queries.
- Backup + restore steps exist and are **testable** (dry-run or staging acceptable).
- Runbook covers restart + recovery without destructive shortcuts as default.

---

## 6. Proof Objects Required

Return:

```text
1. Updated compose excerpt or compose override (paths only if split)
2. Before/after summary for restart policies and limits
3. Short failure-matrix notes (DB / Chroma / worker) with log excerpts or PASS markers
4. Log level / representative log samples (redacted if needed)
5. Backup + restore procedure (commands + order)
6. Operational runbook excerpt (restart + recovery)
7. Git commit hash(es)
```

---

## 7. Engineering Return Format

```text
Directive: 100L
Status: PASS | FAIL | PARTIAL
Commit:
Known Issues:
```

---

## 8. Manifest Link

Parent: Trident Manifest v1.0  
Depends on: **100J** — Deployment + Production Validation  
Unlocks: **100U** — Web UI  

**Renumbering note:** **100L** is **Production Hardening**. IDE **File Lock + Governed Edit** is **100P** (`TRIDENT_IMPLEMENTATION_DIRECTIVE_100P_IDE_FILE_LOCK.md`). **100K** remains IDE bootstrap.

---

END OF DOCUMENT
