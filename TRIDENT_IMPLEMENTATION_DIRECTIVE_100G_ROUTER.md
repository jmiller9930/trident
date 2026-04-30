# TRIDENT IMPLEMENTATION DIRECTIVE 100G
## Router Implementation (Local-First + External Escalation)

---

## 1. Purpose

Implement the routing system that determines whether tasks are executed using the local LLM or escalated to an external API, enforcing strict local-first policy and token optimization.

---

## 2. Scope

Covers:
- Routing decision engine
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
backend/app/router/
  router_service.py
  router_policy.py
  router_logger.py
  token_optimizer.py
  model_adapters/
    local_adapter.py
    external_adapter.py
```

---

## 5. Routing Flow

```text
LangGraph Node → Router → Attempt LOCAL
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

- Router must run inside LangGraph node
- Router must not trigger MCP directly
- Router must not bypass memory system
- Router must not silently escalate

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
Depends on: 100F  
Unlocks: 100H — UI Implementation

---

END OF DOCUMENT
