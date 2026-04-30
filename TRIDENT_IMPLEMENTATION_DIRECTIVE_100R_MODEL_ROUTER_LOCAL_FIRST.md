# TRIDENT IMPLEMENTATION DIRECTIVE 100R
## Model Router — Local-First + External Escalation

```yaml
manifest_id: TRIDENT-MANIFEST-v1.0
project: Project Trident
parent_document: TRIDENT_DOCUMENT_MANIFEST_v1_0.md
document_id: TRIDENT-IMPLEMENTATION-DIRECTIVE-100R
document_type: Directive
sequence: 100R
status: Issued — Deferred (build sequenced after 100G subsystem router)
dependencies:
  - TRIDENT_IMPLEMENTATION_DIRECTIVE_100G_ROUTER.md
  - TRIDENT_DIRECTIVE_000G_ROUTER_POLICY.md
produces:
  - Local/external LLM routing implementation
langgraph_required: true
```

---

## 0. Supersession note

This directive **supersedes** the former **100G** scope that described **local vs external LLM routing**. That material lived in `TRIDENT_IMPLEMENTATION_DIRECTIVE_100G_ROUTER.md` and has been **relocated** here as **100R**.

**100G** now exclusively means the **Subsystem / Work Request Router** (MCP, LANGGRAPH, NIKE, MEMORY read). Do **not** conflate the two layers.

---

## 1. Purpose

Implement the routing system that determines whether tasks are executed using the **local LLM** or **escalated to an external API**, enforcing strict local-first policy and token optimization.

This is **model routing**, not subsystem routing (see **100G**).

---

## 2. Scope

Covers:

- Routing decision engine (**model selection**)
- Local model adapter integration
- External model adapter (stub or controlled call)
- Escalation logic
- Token optimization preprocessor
- Logging and observability

---

## 3. Core Principle

> Local LLM is always attempted first.  
> External LLM is used only when necessary and must be justified.

---

## 4. Required Components

```text
backend/app/model_router/   # recommended package name (avoid collision with 100G subsystem router)
  model_router_service.py
  model_router_policy.py
  model_router_logger.py
  token_optimizer.py
  model_adapters/
    local_adapter.py
    external_adapter.py
```

*(Exact package layout may be adjusted in planning if approved; must not reuse `backend/app/router/` reserved for **100G**.)*

---

## 5. Routing Flow

```text
LangGraph Node → Model Router → Attempt LOCAL
IF insufficient → Evaluate → Escalate to EXTERNAL
```

---

## 6. Local Model Behavior

- Must handle:
  - coding prompts
  - file-aware reasoning
  - simple analysis

- Must return:
  - response
  - confidence score (required)

---

## 7. Escalation Conditions

Escalation occurs if:

- confidence below threshold
- response incomplete
- task flagged as high reasoning
- directive explicitly requires external validation

---

## 8. Token Optimization

Before external call:

System must:

- trim prompt
- remove irrelevant context
- summarize memory
- reduce file scope

---

## 9. Logging Requirements

Each routing decision must log:

```json
{
  "task_id": "T-123",
  "decision": "LOCAL | EXTERNAL",
  "reason": "low_confidence | complex_reasoning | directive_flag",
  "local_model": "model_name",
  "external_model": "model_name"
}
```

---

## 10. Execution Rules

- Model router must run inside LangGraph node
- Model router must not trigger MCP directly
- Model router must not bypass memory system
- Model router must not silently escalate

---

## 11. Hard Constraints

Engineering must NOT:

- default to external model
- bypass logging
- send full context blindly to external API
- expose sensitive data in prompts

---

## 12. Required Tests

- local-first routing test
- escalation trigger test
- token optimization test
- logging validation test

---

## 13. Proof Objects Required

- routing logs
- escalation examples
- token-reduced prompt samples

---

## 14. Acceptance Criteria

- local-first policy enforced
- escalation justified
- token optimization applied
- decisions logged and visible

---

## 15. Manifest Link

Parent: Trident Manifest v1.0  
Depends on: **100G** (subsystem router baseline), **100F**, **000G**  
Unlocks: UI/model observability enhancements as cited in **000G** / **000H** when scheduled  

**Build order:** **100R** is **deferred** until after **100G** subsystem router implementation and acceptance; exact insertion is defined in **Master Execution Guide**.

---

END OF DOCUMENT
