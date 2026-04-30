# TRIDENT IMPLEMENTATION DIRECTIVE 100B
## Schema + Persistence Foundation

---

## 1. Purpose

Implement the first real backend foundation for Trident: schema models, database persistence, migrations, and validation for the core records defined in the architecture directive set.

This directive converts the paper contracts from 000A and 000B into persistent, testable backend structures.

This directive does not authorize LangGraph workflow execution, agent behavior, memory retrieval, MCP execution, router behavior, UI business logic, or file mutation.

---

## 2. Parent Architecture References

This implementation directive is governed by:

- Trident Foundation v1.1
- Trident Document Manifest v1.0
- Directive 000A — Schemas + Graph Contracts
- Directive 000B — Task Ledger + LangGraph State Machine
- Directive 000D — Agent Contracts
- Directive 000K — Engineering Implementation Plan
- Directive 000L — QA + Validation Framework
- Implementation Directive 100A — Repository + Runtime Skeleton

---

## 3. Implementation Scope

Engineering must implement persistent schema support for:

- Directives
- Task ledger entries
- Graph state records
- Agent handoff records
- Proof object metadata
- Audit events
- Basic workspace/project records
- Basic user identity records
- File lock metadata placeholder table

This directive creates the persistence foundation only.

---

## 4. Required Backend Structure

Engineering must add or complete the following backend structure:

```text
backend/
  app/
    models/
      directive.py
      task_ledger.py
      graph_state.py
      handoff.py
      proof_object.py
      audit_event.py
      workspace.py
      project.py
      user.py
      file_lock.py
    schemas/
      directive.py
      task_ledger.py
      graph_state.py
      handoff.py
      proof_object.py
      audit_event.py
      workspace.py
      project.py
      user.py
      file_lock.py
    db/
      session.py
      base.py
      migrations/
    repositories/
      directive_repository.py
      task_ledger_repository.py
      audit_repository.py
    api/
      v1/
        system.py
        directives.py
    tests/
      test_schema_validation.py
      test_persistence.py
      test_audit_events.py
```

Equivalent structure is acceptable only if clearly documented and mapped back to this directive.

---

## 5. Required Database Tables

Engineering must create migrations for the following tables.

### 5.1 users

Minimum fields:

```text
id
display_name
email
role
created_at
updated_at
```

---

### 5.2 workspaces

Minimum fields:

```text
id
name
description
created_by_user_id
created_at
updated_at
```

---

### 5.3 projects

Minimum fields:

```text
id
workspace_id
name
allowed_root_path
git_remote_url
created_at
updated_at
```

---

### 5.4 directives

Minimum fields:

```text
id
workspace_id
project_id
title
status
graph_id
created_by_user_id
created_at
updated_at
```

Status must be constrained to valid lifecycle values.

---

### 5.5 task_ledger

Minimum fields:

```text
id
directive_id
current_state
current_agent_role
current_owner_user_id
last_transition_at
created_at
updated_at
```

Current state must be constrained to valid task lifecycle values.

---

### 5.6 graph_states

Minimum fields:

```text
id
directive_id
graph_id
current_node
state_payload_json
created_at
updated_at
```

This stores serialized graph state only. It does not execute graph logic yet.

---

### 5.7 handoffs

Minimum fields:

```text
id
directive_id
from_agent_role
to_agent_role
handoff_payload_json
requires_ack
acknowledged_at
created_at
```

---

### 5.8 proof_objects

Minimum fields:

```text
id
directive_id
proof_type
proof_uri
proof_summary
proof_hash
created_by_agent_role
created_at
```

---

### 5.9 audit_events

Minimum fields:

```text
id
workspace_id
project_id
directive_id
event_type
event_payload_json
actor_type
actor_id
created_at
```

---

### 5.10 file_locks

Minimum fields:

```text
id
project_id
directive_id
file_path
locked_by_agent_role
locked_by_user_id
lock_status
created_at
expires_at
released_at
```

This is metadata only. Lock enforcement occurs in later implementation directive 100E.

---

## 6. Required Validation Enums

Engineering must define and enforce enums for:

### 6.1 Task Lifecycle State

```text
DRAFT
APPROVED
IN_PROGRESS
REVIEW
REJECTED
CLOSED
FAILED
BLOCKED
```

---

### 6.2 Agent Roles

```text
ARCHITECT
ENGINEER
REVIEWER
DOCUMENTATION
SYSTEM
USER
```

---

### 6.3 Directive Status

```text
DRAFT
ACTIVE
IN_PROGRESS
REVIEW
REJECTED
COMPLETE
CANCELLED
```

---

### 6.4 Proof Object Type

```text
GIT_DIFF
TEST_OUTPUT
EXECUTION_LOG
SCREENSHOT
COMMIT_HASH
DOCUMENTATION_UPDATE
SECURITY_REVIEW
PERFORMANCE_REPORT
BACKUP_RESTORE_PROOF
OTHER
```

---

### 6.5 Audit Event Type

```text
DIRECTIVE_CREATED
STATE_TRANSITION
GRAPH_STATE_WRITTEN
HANDOFF_CREATED
HANDOFF_ACKNOWLEDGED
PROOF_ATTACHED
LOCK_CREATED
LOCK_RELEASED
ROUTER_DECISION
MCP_EXECUTION_REQUESTED
MCP_EXECUTION_COMPLETED
SYSTEM_ERROR
```

---

## 7. API Requirements

Engineering must add minimal API endpoints.

### 7.1 Create Directive

```text
POST /api/v1/directives
```

Creates a directive record and initial task ledger record.

Must also write audit event:

```text
DIRECTIVE_CREATED
```

---

### 7.2 Get Directive

```text
GET /api/v1/directives/{directive_id}
```

Returns directive metadata and current task ledger state.

---

### 7.3 List Directives

```text
GET /api/v1/directives
```

Returns directive summaries.

---

### 7.4 Get System Schema Status

```text
GET /api/v1/system/schema-status
```

Returns whether required tables/migrations are present.

---

## 8. Audit Requirements

Every write operation must produce an audit event.

Minimum required audited operations:

- directive created
- task ledger initialized
- graph state placeholder written
- handoff created
- proof object attached
- file lock metadata created

---

## 9. Hard Constraints

Engineering must not:

- Implement LangGraph execution
- Implement real agent behavior
- Implement memory retrieval
- Implement vector search
- Implement MCP execution
- Implement router escalation
- Implement file mutation
- Implement UI business logic
- Use external APIs
- Store secrets in database
- Bypass audit event creation on writes

---

## 10. Configuration Requirements

Database connection must be configurable through environment variables.

Required example variables:

```text
TRIDENT_DB_HOST=trident-db
TRIDENT_DB_PORT=5432
TRIDENT_DB_NAME=trident
TRIDENT_DB_USER=trident
TRIDENT_DB_PASSWORD=change_me_in_real_env
```

`.env.example` may contain placeholders only.

---

## 11. Migration Requirements

Engineering must provide:

- migration creation command
- migration apply command
- migration rollback command
- clean database initialization command

Migration tool may be Alembic or equivalent.

---

## 12. Required Tests

Engineering must create tests for:

### 12.1 Schema Validation

- valid directive accepted
- invalid status rejected
- invalid agent role rejected
- invalid proof type rejected

---

### 12.2 Persistence

- directive persists
- task ledger persists
- graph state placeholder persists
- audit event persists

---

### 12.3 API

- create directive endpoint succeeds
- get directive endpoint returns current state
- list directives endpoint returns created directive
- schema-status endpoint returns success

---

### 12.4 Audit

- write operations create audit events
- audit event includes directive or project linkage when available

---

### 12.5 Restart Persistence

- create directive
- restart containers
- retrieve directive successfully

---

## 13. Validation Commands

Engineering must provide exact commands used.

Minimum expected commands:

```bash
docker compose build
docker compose up -d
docker compose ps
alembic upgrade head
pytest backend/tests
curl http://localhost:8000/api/v1/system/schema-status
curl http://localhost:8000/api/v1/directives
docker compose restart trident-api
curl http://localhost:8000/api/v1/directives
```

If commands differ, engineering must document the equivalent.

---

## 14. Proof Objects Required

Engineering must return:

```text
1. Git branch name
2. Git commit hash
3. Migration files created
4. Database table list
5. API endpoint proof
6. pytest output
7. Audit event sample
8. Restart persistence proof
9. Confirmation that no business logic outside scope was added
10. Confirmation that no secrets were committed
```

---

## 15. Acceptance Criteria

Directive 100B is accepted only if:

- Required tables exist
- Required enums are enforced
- Required APIs exist
- Directive creation persists correctly
- Task ledger initializes correctly
- Audit events are created for write operations
- Tests pass
- Restart persistence is proven
- No LangGraph execution or agent logic is implemented prematurely
- Git commit exists

---

## 16. Failure Conditions

Reject implementation if:

- Database schema is incomplete
- Migrations are missing
- Invalid states/roles are accepted
- Write operations are not audited
- Directive creation does not initialize task ledger
- Data does not survive restart
- Agent logic is implemented early
- Business logic beyond this directive is added
- Tests are missing
- No commit hash is provided

---

## 17. Engineering Return Format

Engineering must reply in this format:

```text
Directive: 100B
Status: PASS | FAIL | PARTIAL
Branch:
Commit:
Files Created:
Migrations:
Commands Run:
Test Output:
API Proof:
Database Proof:
Audit Proof:
Known Gaps:
Next Recommended Directive:
```

---

## 18. Manifest Link

Parent: Trident Manifest v1.0  
Depends on: 000A–000N, 100A  
Phase: 2  
Unlocks: Implementation Directive 100C — LangGraph Workflow Spine

---

END OF DOCUMENT
