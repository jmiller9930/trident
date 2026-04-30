# TRIDENT DIRECTIVE 000D

## Agent Contracts (Role-Based Execution Definitions)

------------------------------------------------------------------------

## 1. Purpose

Define strict input/output contracts, responsibilities, and enforcement
rules for each agent role within the LangGraph workflow.

------------------------------------------------------------------------

## 2. Scope

Covers: - Architect Agent - Engineer Agent - Reviewer Agent -
Documentation Agent - Input/Output schema per agent - Enforcement
rules - Failure and rejection handling

------------------------------------------------------------------------

## 3. Global Agent Rules

All agents MUST: - Read memory before acting - Acknowledge prior state -
Operate only within LangGraph node - Write output to memory after
execution - Attach proof objects where required

No agent may: - Act outside assigned role - Skip workflow steps - Modify
files outside Git governance

------------------------------------------------------------------------

## 4. Architect Agent

### Responsibilities:

-   Define directive
-   Set acceptance criteria
-   Define required proof objects
-   Initialize LangGraph workflow

### Inputs:

-   User request
-   Project memory

### Outputs:

-   Directive specification
-   Acceptance criteria
-   Graph initialization

------------------------------------------------------------------------

## 5. Engineer Agent

### Responsibilities:

-   Implement code changes
-   Modify files within scope
-   Generate proof artifacts

### Inputs:

-   Directive
-   Project memory
-   File system context

### Outputs:

-   Code changes
-   Git diff
-   Test results
-   Execution logs

------------------------------------------------------------------------

## 6. Reviewer Agent

### Responsibilities:

-   Validate correctness
-   Validate proof artifacts
-   Approve or reject work

### Inputs:

-   Engineer output
-   Directive criteria

### Outputs:

-   Approval or rejection
-   Detailed feedback

------------------------------------------------------------------------

## 7. Documentation Agent

### Responsibilities:

-   Update documentation
-   Record decisions
-   Ensure clarity

### Inputs:

-   Final code state
-   Accepted directive

### Outputs:

-   Updated docs
-   Memory entries

------------------------------------------------------------------------

## 8. Rejection Loop

If Reviewer rejects: - Task returns to Engineer - Engineer must rework -
New proof required

Loop continues until acceptance.

------------------------------------------------------------------------

## 9. Enforcement Rules

-   Single active agent at a time
-   Mandatory handoff acknowledgment
-   Output must match schema
-   Missing proof = automatic rejection

------------------------------------------------------------------------

## 10. Acceptance Criteria

-   All agents follow defined contracts
-   No role overlap or ambiguity
-   Workflow executes deterministically

------------------------------------------------------------------------

## 11. Required Tests

-   Role enforcement tests
-   Input/output validation tests
-   Rejection loop tests

------------------------------------------------------------------------

## 12. Manifest Link

Parent: Trident Manifest v1.0\
Depends on: 000A, 000B, 000C\
Unlocks: 000E

------------------------------------------------------------------------

END OF DOCUMENT
