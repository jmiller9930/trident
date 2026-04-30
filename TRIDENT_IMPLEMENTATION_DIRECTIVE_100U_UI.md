# TRIDENT IMPLEMENTATION DIRECTIVE 100U
## UI Implementation (LangGraph + System State Visualization)

**Renumbering note:** Formerly **`TRIDENT_IMPLEMENTATION_DIRECTIVE_100H_UI.md`** — content preserved; ID **100H** is reserved for **Agent Execution Layer (backend)** (`TRIDENT_IMPLEMENTATION_DIRECTIVE_100H_AGENT_EXECUTION_LAYER.md`).

---

## 1. Purpose

Implement the Trident web UI that reflects real backend state, visualizes LangGraph workflows, and provides full system transparency for users.

---

## 2. Scope

Covers:
- UI layout (left / center / right panels)
- LangGraph visualization
- Directive workspace (chat-style)
- Memory inspection panel
- Git + file lock visibility
- MCP execution + approval UI
- Router decision visibility (subsystem router / **ROUTER_DECISION_MADE**; optional model-router UI when **100R** exists)
- Multi-user awareness (basic)

---

## 3. Core Principle

> The UI must display real system state.  
> No mock or simulated state is allowed.

---

## 4. Required UI Layout

```text
[ LEFT NAV ] [ MAIN WORKSPACE ] [ RIGHT CONTROL PANEL ]
```

---

## 5. Left Navigation Panel

Must include:

- Projects
- Directives
- Agents (status only)
- Memory
- Git
- Execution Logs

---

## 6. Main Workspace

Must support:

- Directive interaction (chat-style)
- Agent messages (Architect / Engineer / Reviewer / Docs)
- Directive status display
- Task timeline (basic)

---

## 7. Right Control Panel

Must display:

### 7.1 LangGraph State
- current node
- completed nodes
- rejection loops

### 7.2 Task State
- lifecycle status
- assigned agent
- owner

### 7.3 Git / Locks
- locked files
- lock owner
- repo status

### 7.4 Execution
- pending MCP commands
- risk level
- approval controls

### 7.5 Router
- subsystem routing decision (local vs external path / target subsystem as exposed by API)
- reason / audit reference

---

## 8. UI Data Binding

UI must call backend APIs (paths per active API version / OpenAPI), including routes equivalent to:

- directives / task ledger
- memory
- git status
- locks
- MCP requests / execution queue
- subsystem router (e.g. route decision logs or `POST /api/v1/router/route` diagnostics as authorized)

---

## 9. Interaction Rules

User CAN:
- create directives
- approve/reject execution
- view memory
- inspect logs

User CANNOT:
- bypass workflow
- edit locked files
- execute commands directly

---

## 10. Hard Constraints

Engineering must NOT:
- simulate state
- hardcode data
- bypass backend APIs
- implement fake workflows

---

## 11. Required Tests

- UI loads with backend data
- state updates reflect in real-time
- LangGraph visualization updates correctly
- approval actions trigger backend updates

---

## 12. Proof Objects Required

- UI screenshots
- API response samples
- state sync validation logs

---

## 13. Acceptance Criteria

- UI reflects backend state
- workflow visible
- system components visible
- no mock data

---

## 14. Manifest Link

Parent: Trident Manifest v1.0  
Depends on: **100L** (Production Readiness & Operational Hardening) — after **100J**  
Unlocks: **100K** — IDE bootstrap (web control plane prerequisite per Master Execution Guide)

---

END OF DOCUMENT
