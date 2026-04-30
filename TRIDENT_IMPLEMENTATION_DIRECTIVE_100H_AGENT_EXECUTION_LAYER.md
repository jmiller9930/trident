# TRIDENT IMPLEMENTATION DIRECTIVE 100H
## Agent Execution Layer (Backend)

```yaml
manifest_id: TRIDENT-MANIFEST-v1.0
project: Project Trident
parent_document: TRIDENT_DOCUMENT_MANIFEST_v1_0.md
document_id: TRIDENT-IMPLEMENTATION-DIRECTIVE-100H
document_type: Directive
sequence: 100H
status: Issued
dependencies:
  - TRIDENT_IMPLEMENTATION_DIRECTIVE_100G_ROUTER.md
  - TRIDENT_DIRECTIVE_000B_TASK_LEDGER_AND_LANGGRAPH_STATE_MACHINE.md
  - TRIDENT_DIRECTIVE_000F_MCP_EXECUTION_LAYER.md
  - TRIDENT_DIRECTIVE_000K_ENGINEERING_IMPLEMENTATION_PLAN.md
produces:
  - Governed agent invocation from LangGraph
  - Agent decision → MCP → receipts → memory/audit (single enforcement path)
langgraph_required: true
```

---

## 0. Scope boundary

**100H** is the **Agent Execution Layer** — **backend only**.

- **No UI responsibilities.** Web UI, panels, and visualization are **100U** (`TRIDENT_IMPLEMENTATION_DIRECTIVE_100U_UI.md`).
- **No** subsystem/work-request routing logic (**100G** owns MCP | LANGGRAPH | NIKE | MEMORY routing).
- **No** LLM model routing (**100R** / **000G**).
- Agents do **not** spawn subprocesses, shell, or bypass MCP for product execution.

---

## 1. Purpose

Introduce a governed **backend** layer where agent roles run **only** when invoked from **compiled LangGraph nodes**, producing structured decisions that may enqueue MCP work and memory writes **solely** through existing services (`MCPService`, `MemoryWriter`) with a complete audit trail.

---

## 2. Core principle

> Controlled agent work **only** through LangGraph → agent → MCP → receipts → governed memory + audit — **no** direct subprocess/shell, file/Git mutation, lock bypass, or MCP bypass.

---

## 3. Required layout (engineering target)

- `backend/app/agents/` — registry, context, executor, service, logging helpers aligned with the accepted plan in **`trident/docs/WORKFLOW_LOG.md`** §100H (Step 2).

---

## 4. Invocation boundary

- Agents run **only** from LangGraph nodes; session/run nonce discipline matches the existing spine.
- `AgentExecutor` (or equivalent) receives directive/task identifiers, `agent_role`, node context, and scoped **read-only** memory views.

---

## 5. Output schema

Structured agent output (e.g. Pydantic) including: `decision`; optional `mcp_request`; optional `memory_write`; `status` ∈ `CONTINUE | COMPLETE | BLOCKED` (exact fields per implementation plan acceptance).

---

## 6. MCP and memory paths

- Any `mcp_request` is translated to the **single** existing MCP execution path (e.g. `MCPExecuteRequest` / `MCPService.execute`).
- Any `memory_write` goes through **`MemoryWriter.write_from_graph`** with the same validations as graph checkpoints (role/nonce alignment).

---

## 7. Auditing

Extend audit event types as needed (e.g. `AGENT_INVOCATION`, `AGENT_DECISION`, `AGENT_MCP_REQUEST`, `AGENT_RESULT`) and tie records to directive/workspace/project identifiers.

---

## 8. Agent roles

Map issued roles (e.g. ENGINEER, REVIEWER, DEBUGGER, DOCS) per registry; align **DOCS** with existing `DOCUMENTATION` or extend enums per program acceptance.

---

## 9. Tests and proof

- Static/import guards: agent modules must not use `subprocess` / `os.system` for product paths.
- Unit/integration tests prove MCP and memory touch only the sanctioned services.
- Proof objects: LangGraph invokes agent node → MCP receipt + memory row + ordered audit chain (details in build phase).

---

## 10. Manifest link

Parent: Trident Manifest v1.0  
Depends on: **100G**  
Unlocks: **100I** — End-to-End System Validation

---

END OF DOCUMENT
