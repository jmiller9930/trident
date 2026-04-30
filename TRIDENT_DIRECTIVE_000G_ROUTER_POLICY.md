# TRIDENT DIRECTIVE 000G

## Local-First Router + External Reasoning Escalation Policy

------------------------------------------------------------------------

## 0. Layering: subsystem router vs model router

- **100G** (`TRIDENT_IMPLEMENTATION_DIRECTIVE_100G_ROUTER.md`): **Subsystem / work-request router** — chooses among **MCP**, **LangGraph**, **Nike**, and **memory read** paths. **No** LLM selection, **no** model escalation.
- **100R** (`TRIDENT_IMPLEMENTATION_DIRECTIVE_100R_MODEL_ROUTER_LOCAL_FIRST.md`): **Model router** — local-first LLM vs external API; **this LLD (000G)** governs **100R** only.
- Do **not** use **000G** to scope **100G** subsystem-router implementation.

------------------------------------------------------------------------

## 0a. Model cadre (policy — implementation: **100R** only)

Trident must support a configurable **model cadre**. The system must **not** assume every agent uses the same LLM.

**Supported modes:**

```text
SINGLE_MODEL_MODE:
  all agents use the same configured local model

CADRE_MODE:
  each agent role may have its own assigned model profile
```

**Required conceptual mapping (profiles, not locked vendor strings):**

```text
Architect → reasoning model
Engineer → coding model
Reviewer → validation / review model
Debugger → diagnostic / code-fix model
Docs → documentation / summarization model
```

**Hardware planning target (initial):**

```text
GPU class: RTX 6000-class, 32GB VRAM
Runtime: local-first
External OpenAI/API: fallback only — not the default execution path
```

**Provisional local / fallback candidates (non-binding until 100R benchmarks validate):**

```text
Architect:
  local_profile: reasoning
  candidate_models:
    - qwen3 reasoning-class 14B/32B quantized
    - deepseek-style reasoning model if compatible
  external_fallback: OpenAI reasoning-class model

Engineer:
  local_profile: coding
  candidate_models:
    - qwen3-coder-next
    - qwen coder-family quantized model
  external_fallback: OpenAI coding-capable model

Reviewer:
  local_profile: validation
  candidate_models:
    - qwen3 reasoning-class model
    - deepseek-style reviewer/reasoning model
  external_fallback: OpenAI reasoning/review model

Debugger:
  local_profile: diagnostic
  candidate_models:
    - qwen3-coder-next
    - qwen coder-family quantized model
  external_fallback: OpenAI coding-capable model

Docs:
  local_profile: documentation
  candidate_models:
    - qwen/gemma-class 7B–14B instruct model
  external_fallback: OpenAI general model
```

**Directive boundaries:**

- **100I** — End-to-end validation: **do not** implement model routing, **do not** treat provisional names as production choices; only ensure the architecture **does not block** future per-agent assignment.
- **100R** — Owns: model profile registry, per-agent assignment, **SINGLE_MODEL_MODE**, **CADRE_MODE**, local-first execution, external fallback policy, fallback-reason logging, token/cost logging, model health checks, benchmark/fit validation for 32GB-class targets.
- **Forbidden:** implementing model routing inside Nike, MCP, or the IDE; hard-coding final production models before **100R** acceptance tests.

------------------------------------------------------------------------

## 1. Purpose

Define the routing system responsible for selecting between local LLM
execution and external API escalation, enforcing cost-aware,
capability-aware decision-making.

------------------------------------------------------------------------

## 2. Scope

Covers: - Local vs external model selection - Escalation logic - Token
optimization - Routing visibility - Logging and observability

------------------------------------------------------------------------

## 3. Core Principle

> Local LLM is always primary.\
> External LLM is used only when required.

------------------------------------------------------------------------

## 4. Routing Flow

``` text
LangGraph Node → Router → Decision:
    LOCAL → Execute
    IF insufficient → EXTERNAL → Execute
```

------------------------------------------------------------------------

## 5. Task-Based Routing

### LOCAL (default)

-   Coding / repo edits
-   File analysis
-   RAG queries
-   Routine reasoning

### EXTERNAL (fallback only — after local attempt)

Use external APIs **only** when local execution is insufficient or fails — never as the default path. Typical triggers include:

-   Complex architecture reasoning beyond local confidence threshold
-   Adversarial validation
-   High-context reasoning beyond local context limits
-   Local failure or health degradation

------------------------------------------------------------------------

## 6. Escalation Triggers

-   Low confidence output
-   Incomplete solution
-   Context window limitations
-   Explicit directive requirement

------------------------------------------------------------------------

## 7. Token Optimization Rules

Before external call: - Compress context - Remove irrelevant data -
Summarize memory - Deduplicate input - Limit file scope

------------------------------------------------------------------------

## 8. Logging Requirements

Each routing decision must log:

``` json
{
  "event": "ROUTER_DECISION",
  "task_id": "T-123",
  "decision": "LOCAL | EXTERNAL",
  "reason": "string",
  "local_model": "model_name",
  "external_model": "model_name"
}
```

------------------------------------------------------------------------

## 9. UI Visibility

System must display: - Routing decision - Escalation reason - Model
used - Token usage (future)

------------------------------------------------------------------------

## 10. Constraints

-   No silent escalation
-   No external-first logic
-   No direct execution bypass

------------------------------------------------------------------------

## 11. Integration with LangGraph

-   Router executes within node
-   Output determines next state
-   Decisions stored in memory

------------------------------------------------------------------------

## 12. Acceptance Criteria

-   Local-first enforced
-   Escalation justified and logged
-   Token usage minimized
-   Decisions visible to user

------------------------------------------------------------------------

## 13. Required Tests

-   Routing decision tests
-   Escalation condition tests
-   Token optimization tests
-   Logging validation tests

------------------------------------------------------------------------

## 14. Manifest Link

Parent: Trident Manifest v1.0\
Depends on: 000A--000F\
Unlocks: 000H

------------------------------------------------------------------------

END OF DOCUMENT
