# TRIDENT IMPLEMENTATION DIRECTIVE 100O
## Nike Event Orchestrator (Implementation)

---

## 1. Purpose

Implement **Nike**, Trident’s internal **non-intelligent** event orchestration layer, as defined in **Directive 000P — Nike Event Orchestrator**.

Nike provides:

- Event ingestion and persistence
- Deterministic routing from event types to handlers
- Retry and dead-letter behavior for orchestration reliability
- Notification outbox for downstream consumers (UI/IDE/webhooks — wiring may be stubbed where no consumer exists yet)
- **LangGraph wakeup / trigger integration** without replacing LangGraph as workflow authority

This directive does **not** authorize memory system implementation (**100D**), MCP execution, router product logic, autonomous agents, LLM calls, file or Git mutation, or bypassing LangGraph state transitions.

---

## 2. Parent Architecture References

This implementation directive is governed by:

- Trident Document Manifest v1.0
- **Directive 000P — Nike Event Orchestrator** (authoritative product definition)
- Directive 000B — Task Ledger + LangGraph State Machine (authority boundaries)
- Implementation Directive **100B** — Schema + Persistence Foundation
- Implementation Directive **100C** — LangGraph Workflow Spine
- Trident Master Execution Guide v1.1 (spine order **100C → 100O → 100D**)

---

## 3. Core Principle

> Nike coordinates **events**. Nike does **not** reason, execute shell commands, call LLMs, mutate files, approve MCP actions, or decide workflow outcomes.

LangGraph remains the workflow authority (**000P §8**). Nike may **dispatch** events and **trigger** graph evaluation per policy; it may not skip nodes, force closure, or replace ledger/graph truth.

---

## 4. Runtime Placement (Authoritative)

| Component | Role |
|-----------|------|
| **trident-api** | Ingest events (HTTP API), persist accepted events, **enqueue** for processing. **Not** the default long-running dispatcher loop. |
| **trident-worker** | **Default Nike dispatcher runtime**: poll/process pending events, invoke handlers, retries, DLQ moves, outbox progression, structured logs. |

Engineering **must** implement the dispatcher loop in **`trident-worker`** (or a dedicated worker entrypoint shipped in the worker image). Short-lived administrative tasks may exist in the API (e.g. manual replay **only if** explicitly scoped and audited); **continuous orchestration processing runs in the worker**.

---

## 5. Event Envelope (Required)

Every Nike-persisted event **must** conform to this minimum envelope (**000P §6**):

```json
{
  "event_id": "uuid",
  "event_type": "DIRECTIVE_CREATED",
  "source": "trident-api",
  "workspace_id": "uuid",
  "project_id": "uuid",
  "directive_id": "uuid",
  "task_id": "uuid",
  "correlation_id": "uuid",
  "payload": {},
  "created_at": "iso8601"
}
```

Implementation may store columns + JSON `payload`; unknown envelope fields must not be dropped without versioning strategy.

**Idempotency:** `event_id` is the idempotency key for ingest (**000P §13**). Duplicate `event_id` must not create duplicate processing outcomes (reject or no-op with recorded outcome).

---

## 6. Required Event Types (Minimum Support)

Nike **must** accept and persist at least the types listed in **000P §7**. For **100O**, routing handlers may **no-op with audit/log** for types that depend on subsystems not yet implemented (memory, MCP, router), **provided** events are stored, attempts tracked, and behavior documented.

Minimum subset that **must** have real routing behavior in **100O** (exact list fixed at build time in engineering notes):

- **`DIRECTIVE_CREATED`** → enqueue downstream handling path that leads to **LangGraph wakeup** per §15 (must not bypass graph).
- Additional types as stubs or passthrough per §11.

---

## 7. Required Database Tables

Engineering must create migrations for Nike persistence (**000P §14**). Minimum tables:

### 7.1 `nike_events`

Stores accepted events (envelope + payload).

Minimum fields:

```text
id (uuid, pk)
event_id (uuid, unique)           -- idempotency key
event_type (text, indexed)
source (text)
workspace_id (uuid, nullable, indexed)
project_id (uuid, nullable, indexed)
directive_id (uuid, nullable, indexed)
task_id (uuid, nullable, indexed)
correlation_id (uuid, nullable, indexed)
payload_json (jsonb/json)
status (text)                     -- e.g. PENDING, DISPATCHED, FAILED, DEAD_LETTER, COMPLETED
created_at (timestamptz)
updated_at (timestamptz)
```

### 7.2 `nike_event_attempts`

Retry / delivery attempts per event.

```text
id (uuid, pk)
event_pk (uuid, fk → nike_events.id)
attempt_no (int)
outcome (text)                    -- SUCCESS, RETRY_SCHEDULED, FAILED
error_detail (text, nullable)
created_at (timestamptz)
```

### 7.3 `nike_dead_letter_events`

Dead-lettered events after bounded retries.

```text
id (uuid, pk)
event_pk (uuid, fk)
reason (text)
failed_attempt_count (int)
payload_snapshot_json (json)
created_at (timestamptz)
```

### 7.4 `nike_notification_outbox`

Downstream notifications (UI/IDE/internal subscribers).

```text
id (uuid, pk)
event_pk (uuid, fk, nullable)
channel (text)                    -- e.g. UI, IDE, INTERNAL
notification_type (text)
payload_json (json)
status (text)                     -- PENDING, SENT, FAILED
created_at (timestamptz)
sent_at (timestamptz, nullable)
```

Indexes must support query by **directive_id**, **project_id**, **event_type**, **correlation_id**, **created_at** (**000P §14**).

---

## 8. Ingest API (trident-api)

Engineering must expose a minimal authenticated ingest surface:

```text
POST /api/v1/nike/events
```

Responsibilities:

- Validate envelope + payload schema (reject malformed requests).
- Enforce idempotency on `event_id`.
- Persist to `nike_events` with status **PENDING** (or equivalent initial state).
- **Must not** run the full dispatcher loop as the default code path; worker picks up pending rows.

Optional:

```text
GET /api/v1/nike/events/{event_id}
GET /api/v1/nike/events?directive_id=...
```

Read endpoints are recommended for operations and proof; scope may be minimal if timeboxed.

---

## 9. Dispatcher (trident-worker)

The worker **must**:

- Poll or dequeue **PENDING** events on an interval (configurable env, e.g. `TRIDENT_NIKE_POLL_SEC`).
- For each event, run the **routing table**: `event_type` → handler function.
- Record attempts in `nike_event_attempts`.
- On transient failure: bounded retries with backoff policy (**000P §13**); policy constants documented.
- On exhaustion: move to `nike_dead_letter_events` and update parent status.
- Emit structured logs: received, dispatched, retry, failed, dead-lettered (**000P §16**), each with **correlation_id** when present.

Handlers **must**:

- Be deterministic routing glue only (no LLM, no shell execution, no file/Git mutation).
- Invoke LangGraph **only** through approved integration (**§15**).

---

## 10. Retry / DLQ Behavior

- **Bounded retries** per event type or global default (engineering must document numbers).
- **Dead-letter** records must remain queryable and auditable.
- **At-least-once** semantics allowed (**000P §13**); handlers must tolerate duplicate dispatch safeguards where feasible (idempotent side effects or guards).

---

## 11. Notification Outbox

- Workers **must** append outbox rows when routing requires notification per policy (may be minimal in **100O**).
- No fake delivery: status must reflect actual send attempts or explicit **SKIPPED/NOT_CONFIGURED** if no channel exists (**000P §15** intent).

---

## 12. LangGraph Wakeup Boundary

- Nike **may** trigger or wake LangGraph evaluation (**000P §4.1, §8**).
- Nike **must not** decide workflow outcomes, skip nodes, or force closure (**000P §8**).
- Approved integration for **100O** (exact entrypoint fixed at build time):

  - Handlers may call existing **`run_spine_workflow`** (or successor API internal function) **only** where event semantics map to “start/continue workflow” and **ledger/graph remain authoritative**.
  - Broader fine-grained “per-node” triggering **beyond** current **100C** packaging is **out of scope** unless explicitly expanded in a future directive revision; Nike must not invent parallel workflow engines.

Any LangGraph invocation **must** be observable via existing task ledger / graph state / audit pathways (**100B/100C**).

---

## 13. Hard Constraints (Non-Agent)

Engineering must **NOT**:

- Implement **100D** memory storage/retrieval product logic.
- Call LLMs or expose model routing decisions inside Nike.
- Execute MCP tools or approve MCP actions from Nike.
- Mutate Git or filesystem state from Nike handlers.
- Implement UI business logic (beyond emitting outbox rows / minimal stubs).
- Bypass LangGraph for lifecycle transitions.

---

## 14. Configuration

Required environment variables (examples; names may vary if documented):

```text
TRIDENT_DB_*                         -- Postgres (existing)
TRIDENT_NIKE_POLL_SEC=             -- worker poll interval
TRIDENT_NIKE_MAX_ATTEMPTS=         -- retry ceiling before DLQ
TRIDENT_LOG_LEVEL=
```

---

## 15. Required Tests

Engineering must add tests for:

- Envelope validation (valid accepted; invalid rejected).
- Idempotent ingest (duplicate `event_id` behavior).
- Dispatcher picks up pending events (integration-style against SQLite or Postgres test DB).
- Retry path increments attempts; DLQ after bound.
- Outbox row creation where applicable.
- **Proof of non-bypass:** handlers do not mutate authoritative tables except via declared integrations (assert-level or architectural tests per engineering judgment).

---

## 16. Proof Objects Required

Engineering must return:

```text
1. Git branch name
2. Git commit hash
3. Migration files created (Nike tables)
4. Sample ingest response + persisted row identifiers
5. Worker dispatch logs (structured) showing correlation_id
6. DLQ proof (forced failure test acceptable)
7. LangGraph wakeup proof (event → workflow invocation path) without bypass
8. clawbot Postgres proof (see §17)
9. Confirmation: no LLM/MCP/file/Git/agent-memory logic added
```

---

## 17. clawbot Proof Requirements (Mandatory)

Same governed execution chain as prior directives:

```text
local → commit → push → clawbot → pull → run → prove
```

Minimum operational proof on **clawbot** (real Postgres, Docker Compose):

1. `git pull origin main` at deployed checkout; record **HEAD**.
2. `docker compose up -d --build` from compose directory.
3. **POST** ingest to **`/trident/api/v1/nike/events`** (when `TRIDENT_BASE_PATH=/trident`) with a valid envelope.
4. Show **`nike_events`** row persisted (psql or API GET).
5. Show **worker** processing event (logs) within bounded time.
6. **Restart proof:** `docker compose restart trident-worker` (and optionally `trident-api`), then demonstrate pending/failed semantics remain consistent or processing resumes per policy.
7. Capture **`docker compose ps`** showing healthy stack.

SQLite-only tests are **not** sufficient for final acceptance.

---

## 18. Acceptance Criteria

Directive **100O** is accepted only if:

- Tables exist and migrations apply cleanly on Postgres.
- Ingest API persists events idempotently.
- **Worker-based dispatcher** runs as default processing engine (**§4**).
- Retry/DLQ/outbox behaviors match documented policy.
- LangGraph boundary respected (**§12**).
- Tests pass.
- **clawbot proof** (**§17**) passes.
- No forbidden behaviors (**§13**).

---

## 19. Failure Conditions

Reject implementation if:

- Dispatcher runs primarily inside API request lifecycle as default.
- Events bypass persistence or idempotency.
- LangGraph or ledger truth is bypassed.
- Memory (**100D**), MCP execution, or agent reasoning appears inside Nike.
- No worker proof or no Postgres proof.

---

## 20. Engineering Return Format

Engineering must reply:

```text
Directive: 100O
Status: PASS | FAIL | PARTIAL
Branch:
Commit:
Files Created:
Migrations:
Commands Run:
Test Output:
clawbot Proof Summary:
Known Gaps:
Next Recommended Directive:
```

---

## 21. Manifest Link

Parent: Trident Manifest v1.0  
Depends on: **000P**, **100B**, **100C**  
Phase: Spine (orchestration)  
Unlocks: **100D** — Memory System Implementation (after Nike acceptance)

---

END OF DOCUMENT
