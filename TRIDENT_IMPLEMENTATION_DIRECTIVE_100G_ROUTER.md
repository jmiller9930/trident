# TRIDENT IMPLEMENTATION DIRECTIVE 100G
## Subsystem Router / Work Request Router

```yaml
manifest_id: TRIDENT-MANIFEST-v1.0
project: Project Trident
parent_document: TRIDENT_DOCUMENT_MANIFEST_v1_0.md
document_id: TRIDENT-IMPLEMENTATION-DIRECTIVE-100G
document_type: Directive
sequence: 100G
status: Issued
dependencies:
  - TRIDENT_IMPLEMENTATION_DIRECTIVE_100F_MCP_EXECUTION.md
  - TRIDENT_DIRECTIVE_000P_NIKE_EVENT_ORCHESTRATOR.md
  - TRIDENT_DIRECTIVE_000B_TASK_LEDGER_AND_LANGGRAPH_STATE_MACHINE.md
produces:
  - Subsystem routing decisions (MCP, LANGGRAPH, NIKE, MEMORY read)
langgraph_required: true
```

---

## 0. What this directive is **not**

This **100G** implementation directive defines **only** the **Subsystem / Work Request Router**:

- **No** LLM routing, **no** model selection, **no** external API escalation (those belong to **000G** + **100R** — Model Router).
- **No** command execution ( **MCP executes** ).
- **No** MCP **risk** classification (risk tiers live in **100F** MCP layer).
- **No** memory **writes** (memory informs via **read** routing only; writes stay graph/MCP-governed).
- **No** subprocess / shell / file mutation.

Confusion cleared: former Markdown in this filename that described **local/external LLM routing** has been moved to **`TRIDENT_IMPLEMENTATION_DIRECTIVE_100R_MODEL_ROUTER_LOCAL_FIRST.md`**.

---

## 1. Purpose

Introduce a **central routing layer** that determines:

- where work goes  
- which subsystem handles it  
- how execution paths are selected  

This layer **decides**; it does **not** execute.

---

## 2. Orchestration rule

```text
Router decides.
MCP executes.
LangGraph governs.
Nike coordinates.
Locks enforce.
Memory informs.
```

**No overlap:** the subsystem router returns a **decision object** and audit record only; callers invoke the appropriate subsystem entrypoints.

---

## 3. Responsibilities

The router must:

- receive a structured work request  
- **classify intent** for **subsystem routing** (not operational risk — MCP owns risk)  
- route to exactly one of:
  - **LangGraph** workflow path  
  - **MCP** execution path  
  - **Nike** event path  
  - **Memory** read path  
- produce a routing decision object  
- log the decision (**ROUTER_DECISION_MADE**)

---

## 4. Non-responsibilities (hard rules)

The subsystem router must **NOT**:

- execute commands  
- call subprocess / shell  
- bypass MCP for execution intent  
- modify files  
- perform memory writes  
- run workflows internally (may only reference **LangGraph entrypoints**, not embed graph execution)  
- perform MCP-style **risk** classification  

Ambiguity **fails closed** (`validated: false`, no safe route).

---

## 5. Required modules

```text
backend/app/router/
  router_service.py
  router_classifier.py
  router_validator.py
  router_logger.py
```

(`router` here means **subsystem router** only.)

---

## 6. Input contract

```text
directive_id
task_id
agent_role
intent
payload        # optional structured JSON
```

---

## 7. Output contract

```json
{
  "route": "MCP | LANGGRAPH | NIKE | MEMORY",
  "reason": "...",
  "next_action": "...",
  "validated": true
}
```

`next_action` describes the **recommended** API entry or operation id for the caller — **not** an executed side effect.

---

## 8. Decision boundaries

- **Execution intent → MCP**  
- **Workflow progression → LANGGRAPH**  
- **Event propagation → NIKE**  
- **Read-only knowledge → MEMORY**

---

## 9. Logging

Every routing decision must emit audit event:

```text
ROUTER_DECISION_MADE
```

with full reasoning payload (intent, route, reason, ids — no secrets).

---

## 10. Tests

- correct routing by intent  
- invalid input rejection  
- no execution side-effects  
- no bypass paths  

---

## 11. Proof

Must show:

- routing decisions for all four routes  
- audit logs (**ROUTER_DECISION_MADE**)  
- no execution performed  
- no unauthorized state mutation  

---

## 12. Governed execution

1. **Step 1 — Read**  
2. **Step 2 — Plan** (required before build)  
3. **Step 3 — Build** only after plan acceptance  

Documentation conflict against legacy LLM **100G** text is **resolved** via **100R** relocation (see **DOC_100G_CONFLICT_RESOLUTION** in **`WORKFLOW_LOG.md`**).

---

## 13. Manifest Link

Parent: Trident Manifest v1.0  
Depends on: **100F**  
Unlocks: **100H** — Agent Execution Layer (backend; `TRIDENT_IMPLEMENTATION_DIRECTIVE_100H_AGENT_EXECUTION_LAYER.md`). Web UI is **100U** (`TRIDENT_IMPLEMENTATION_DIRECTIVE_100U_UI.md`).  

**Related (deferred):** **100R** — Model Router / local-first external escalation (**000G**).

---

END OF DOCUMENT
