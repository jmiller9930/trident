# TRIDENT IMPLEMENTATION DIRECTIVE 100N
## IDE Agent Workflow Integration (LangGraph-Driven Cursor Behavior)

---

## 1. Purpose

Integrate full agent-driven workflows into the Trident IDE, ensuring that all Cursor-style interactions (chat, edits, tasks) are governed by LangGraph, memory, and backend enforcement.

This is the directive that transforms the IDE from a viewer into a true agent-powered development environment.

---

## 2. Scope

Covers:
- Chat → directive mapping
- Agent role execution inside IDE
- LangGraph node awareness in IDE
- Task lifecycle integration
- Memory-aware responses
- Patch workflow integration (100M)
- MCP request surfacing (100F)
- Subsystem router visibility (**100G**)

---

## 3. Core Principle

> Every IDE action must map to a LangGraph-controlled task.

No free-form AI execution is allowed.

---

## 4. Interaction Model

```text
User input (chat / command)
→ IDE sends to backend
→ Backend creates/updates directive
→ LangGraph executes node
→ Response returned to IDE
→ IDE displays agent output
```

---

## 5. Agent Roles in IDE

IDE must represent:

- Architect
- Engineer
- Reviewer
- Documentation

Each response must show:
- agent role
- directive ID
- task state
- node stage

---

## 6. Chat Behavior

Chat must support:

- Ask (read-only)
- Propose change (patch)
- Execute task (directive)
- Request review
- Update docs

Each action must trigger backend workflow.

---

## 7. Directive Binding

Each chat session must bind to:

- a directive_id
- a project_id
- a task lifecycle state

No orphan chat allowed.

---

## 8. Memory Integration

IDE must:
- fetch relevant memory
- display context
- show prior decisions

Memory writes must occur via backend only.

---

## 9. Patch Integration

From 100M:

- agent proposes patch
- user reviews
- apply triggers backend validation

---

## 10. MCP Integration

IDE must display:
- pending execution requests
- risk classification
- approval UI

---

## 11. Router Visibility

IDE must show:
- LOCAL vs EXTERNAL decision
- reason
- model used

---

## 12. UI Updates

IDE must dynamically update:

- current LangGraph node
- directive state
- agent transitions
- proof requirements

---

## 13. Hard Constraints

Engineering must NOT:
- allow direct AI execution outside LangGraph
- allow edits outside patch system
- allow task completion without backend approval
- allow memory writes from IDE directly

---

## 14. Required Tests

- chat triggers directive creation
- agent roles enforced
- lifecycle progression works
- memory visible and consistent
- MCP requests surface correctly

---

## 15. Proof Objects Required

- chat → directive mapping logs
- agent execution logs
- lifecycle trace
- UI screenshots showing state transitions

---

## 16. Acceptance Criteria

- IDE fully integrated with backend workflows
- all actions tied to directives
- agent roles enforced
- no free-form execution paths

---

## 17. Manifest Link

Parent: Trident Manifest v1.0  
Depends on: 100M  
Unlocks: FINAL SYSTEM — Cursor-Equivalent Trident IDE Complete

---

END OF DOCUMENT
