# TRIDENT IMPLEMENTATION DIRECTIVE 100F
## MCP Execution Implementation (Controlled Execution Layer)

---

## 1. Purpose

Implement the MCP (Model Context Protocol) execution layer that safely handles all command execution, ensuring no direct agent-to-system execution occurs outside governed pathways.

---

## 2. Scope

Covers:
- MCP request handling
- Command classification
- Approval system
- Execution adapters (local stub + SSH stub)
- Execution logging
- Error handling
- Receipt generation

---

## 3. Core Principle

> No command executes unless it passes through MCP.

---

## 4. Required Components

### 4.1 MCP Service

```text
backend/app/mcp/
  mcp_service.py
  mcp_router.py
  mcp_validator.py
  mcp_logger.py
```

---

### 4.2 Execution Adapters

```text
backend/app/mcp/adapters/
  local_adapter.py
  ssh_adapter.py
```

NOTE: SSH adapter is stubbed only (no real remote execution yet).

---

## 5. Execution Flow

```text
LangGraph Node → MCP Request → Classification → Approval Gate → Execution → Result → Memory + Audit
```

---

## 6. Command Classification

Commands must be classified as:

- LOW
- MEDIUM
- HIGH

---

## 7. Approval Rules

- LOW → auto-approve (configurable)
- MEDIUM → log + optional approval
- HIGH → must require approval flag

No HIGH command may run without explicit approval.

---

## 8. Execution Behavior (THIS PHASE)

- Simulate execution
- Return structured result
- Capture stdout/stderr placeholders
- Generate execution receipt

DO NOT execute destructive commands.

---

## 9. Execution Receipt Format

```json
{
  "task_id": "T-123",
  "command": "pytest",
  "risk": "LOW",
  "approved": true,
  "status": "success",
  "output": "simulated output"
}
```

---

## 10. Logging Requirements

Must log:

- execution_requested
- execution_classified
- execution_approved / rejected
- execution_completed
- execution_failed

---

## 11. Hard Constraints

Engineering must NOT:
- allow shell execution outside MCP
- bypass approval gate
- perform real destructive execution
- expose secrets in logs

---

## 12. Required Tests

- classification test
- approval gate test
- execution receipt test
- rejection path test

---

## 13. Proof Objects Required

- execution logs
- classification logs
- approval logs
- receipt samples

---

## 14. Acceptance Criteria

- all execution flows through MCP
- classification works
- approval enforced
- receipts generated
- no direct execution paths exist

---

## 15. Manifest Link

Parent: Trident Manifest v1.0  
Depends on: 100E  
Unlocks: 100G — Router Implementation

---

END OF DOCUMENT
