# TRIDENT DIRECTIVE 000G

## Local-First Router + External Reasoning Escalation Policy

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

### EXTERNAL (allowed)

-   Complex architecture reasoning
-   Adversarial validation
-   High-context reasoning
-   Local failure

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
