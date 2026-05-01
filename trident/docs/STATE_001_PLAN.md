# STATE_001_PLAN — State Schema + Transition Foundation

**Directive:** `STATE_001`  
**Parent LLD:** `trident/docs/APP_LLD_001.md`  
**Parent blueprint:** `trident/docs/APP_BLUEPRINT_001.md` (STATE_ENGINE addendum)  
**Status:** **READY**

---

## Plan summary

Establish **database schema** and **additive enums** for the directive/project state machine and **project gates**. No **StateTransitionService** implementation, **no UI**, **no agent behavior** changes in this slice.

---

## Schema changes

### Enums (Python `StrEnum` — persisted as strings in existing columns)

| Enum | Change |
|------|--------|
| **`DirectiveStatus`** | Add: `ISSUED`, `ACKNOWLEDGED`, `PLANNING`, `PLAN_ACCEPTED`, `BUILDING`, `PROOF_RETURNED`, `PROOF_ACCEPTED`, `BUG_CHECKING`, `SIGNED_OFF`, `NEXT_ISSUED`, `BLOCKED` — **additive**; legacy values unchanged |
| **`TaskLifecycleState`** | Add: `PROOF_RETURNED`, `BUG_CHECKING`, `SIGNED_OFF` — **additive** |
| **`GateStatus`** | New: `READY`, `MISSING`, `DEGRADED`, `WAIVED`, `BLOCKING` (`app/models/state_enums.py`) |
| **`ProjectGateType`** | New: `PLAN`, `STRUCTURE`, `PREREQS` |
| **`StateTransitionActorType`** | New: `USER`, `AGENT`, `SYSTEM` (log column uses string; aligns with audits) |

### Tables

| Table | Purpose |
|-------|---------|
| **`state_transition_log`** | Append-only: `id`, `directive_id` (nullable FK), `from_state`, `to_state`, `actor_type`, `actor_id`, `correlation_id`, `reason`, `created_at` |
| **`project_gates`** | One row per `(project_id, gate_type)` unique: `status`, `approved_by`, `approved_at`, `waiver_flag`, `waiver_reason`, timestamps |

**Note:** `directive_id` nullable supports future project-scoped transitions logged without a directive row.

---

## Migration steps

| Step | Action |
|------|--------|
| 1 | Alembic revision **`state001001`** revises **`fix003001`** |
| 2 | `upgrade()`: create **`state_transition_log`**, **`project_gates`** + indexes + FKs |
| 3 | `downgrade()`: drop tables (order: project_gates, state_transition_log) |
| 4 | Run `alembic upgrade head` in each environment |

**Non-destructive:** no ALTER on `directives` / `task_ledger` required for enum extension (values are strings).

---

## Compatibility notes

- Existing **`directives.status`** and **`task_ledger.current_state`** rows **unchanged** at rest.  
- New enum members are **optional** for callers until **STATE_002** centralizes transitions.  
- **Open question (defer):** REST namespace `/v1/projects` vs `/v1/workbench` — no API in STATE_001.  
- **Open question (defer):** `project_gates.project_id` uses existing **`projects`** table (already FK from `directives`); **`workspace_id`** bridge not required for this migration.

---

## Risks

| Risk | Mitigation |
|------|------------|
| String length | `from_state`/`to_state` **64** chars; directive status column **32** — new status values fit (**≤15** chars) |
| Orphan log rows | `directive_id` **ON DELETE SET NULL** preserves history if directive removed |
| Duplicate gate rows | **UniqueConstraint** `(project_id, gate_type)` |

---

## Proof plan

| Proof | Method |
|-------|--------|
| Migration applies | `alembic upgrade head` on clean DB + CI |
| ORM load | Import `StateTransitionLog`, `ProjectGate`; metadata creates expected tables in tests if using `create_all` |
| Regression | Existing **`pytest`** spine + persistence suites **pass** |

---

## RETURN

| Field | Value |
|--------|--------|
| **Directive** | `STATE_001_PLAN` |
| **Status** | **READY** |
| **Implementation** | `state001001_state_engine_foundation.py`, models under `app/models/` |
