# TRIDENT DIRECTIVE 000F

## MCP Execution Layer (Governed Execution & Tooling)

------------------------------------------------------------------------

## 1. Purpose

Define the Model Context Protocol (MCP) execution layer responsible for
safe, governed interaction with external systems including SSH, vCenter,
file systems, and runtime environments.

------------------------------------------------------------------------

## 2. Scope

Covers: - Command execution via SSH - Infrastructure interaction
(vCenter, Docker, APIs) - Tool abstraction layer - Approval system -
Execution logging - Risk classification

------------------------------------------------------------------------

## 3. Core Principle

> No agent may execute commands directly.\
> All execution must pass through MCP.

------------------------------------------------------------------------

## 4. Execution Flow

``` text
Agent → LangGraph Node → MCP Request → Approval Gate → Execution → Result → Memory
```

------------------------------------------------------------------------

## 5. Execution Types

### 5.1 Local Execution

-   File operations
-   Test execution
-   Build processes

### 5.2 Remote Execution

-   SSH commands
-   Remote scripts
-   Deployment operations

### 5.3 Infrastructure Execution

-   vCenter operations
-   Container orchestration
-   API calls

------------------------------------------------------------------------

## 6. Command Classification

Each command must be classified:

-   LOW RISK: Read-only, tests
-   MEDIUM RISK: Local modifications
-   HIGH RISK: Infra changes, remote execution

------------------------------------------------------------------------

## 7. Approval System

### Required Behavior:

-   LOW RISK: auto-approved (configurable)
-   MEDIUM RISK: user approval recommended
-   HIGH RISK: user approval required

------------------------------------------------------------------------

## 8. Execution Constraints

-   No destructive command without approval
-   No root-level execution unless explicitly allowed
-   All commands must be logged
-   All outputs must be captured

------------------------------------------------------------------------

## 9. Execution Logging

Each execution must log:

``` json
{
  "task_id": "T-123",
  "agent": "Engineer",
  "command": "pytest",
  "target": "local",
  "risk_level": "LOW",
  "approved": true,
  "result": "success"
}
```

------------------------------------------------------------------------

## 10. Error Handling

-   Capture stderr/stdout
-   Return structured error objects
-   Trigger retry or rejection path in LangGraph

------------------------------------------------------------------------

## 11. Security Rules

-   SSH keys must be managed securely
-   No plaintext secrets
-   Access scoped per project
-   All actions auditable

------------------------------------------------------------------------

## 12. Integration with LangGraph

-   Execution occurs within node
-   Results determine next state
-   Failures trigger rejection or retry

------------------------------------------------------------------------

## 13. Acceptance Criteria

-   All execution routed through MCP
-   Approval gates enforced
-   Logging complete and accurate
-   Security constraints enforced

------------------------------------------------------------------------

## 14. Required Tests

-   Command execution tests
-   Approval workflow tests
-   Logging validation tests
-   Error handling tests

------------------------------------------------------------------------

## 15. Manifest Link

Parent: Trident Manifest v1.0\
Depends on: 000A, 000B, 000C, 000D, 000E\
Unlocks: 000G

------------------------------------------------------------------------

END OF DOCUMENT
