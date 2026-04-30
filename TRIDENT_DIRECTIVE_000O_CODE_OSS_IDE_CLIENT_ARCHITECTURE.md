# TRIDENT DIRECTIVE 000O
## Code - OSS IDE Client Architecture (Cursor-Style Frontend + Shared Backend)

---

## 1. Purpose

Define the Trident IDE architecture that provides a Cursor-like local developer experience using a Code - OSS based frontend connected to the Trident backend control plane.

This directive updates the Trident product boundary:

> Trident is not only a web control plane.  
> Trident includes a local IDE client based on Code - OSS / VS Code architecture, backed by the shared Trident web/API backend.

---

## 2. Core Product Lock

Trident must provide:

```text
Local IDE Frontend  +  Shared Web Backend  +  LangGraph Agent Control Plane
```

The IDE is the primary developer surface.

The backend remains the system of record for:

- projects
- memory
- directives
- agent workflows
- Git governance
- file locks
- proof objects
- team collaboration
- local/external model routing
- MCP execution approvals

---

## 3. Architecture Model

```text
Trident Code - OSS IDE Client
        ↓
Trident IDE Extension / Client Bridge
        ↓
Trident API Gateway
        ↓
LangGraph Workflow Engine
        ↓
Shared Memory + Task Ledger
        ↓
Git/File Lock Governance
        ↓
MCP Execution Layer
        ↓
Local LLM / External API Router
```

The IDE must never become an isolated brain. It is a client of the backend control plane.

---

## 4. Required Frontends

Trident has two supported user interfaces:

### 4.1 Trident IDE Client

Purpose:
- Cursor-like coding experience
- local project editing
- inline code assistance
- repo-aware chat
- agent task panel
- file lock awareness
- Git status awareness
- memory-aware code work

### 4.2 Trident Web Client

Purpose:
- team control plane
- directive board
- agent workflow visualization
- approvals
- memory inspection
- proof review
- admin/project management

Both clients consume the same backend state.

No separate state systems are allowed.

---

## 5. Backend as Collaboration + Repo Control Plane

The backend is not merely an API server.

The backend is the shared authority for:

- project registration
- allowed project roots
- Git repository state
- branch status
- file lock ownership
- directive lifecycle
- agent handoffs
- memory storage/retrieval
- proof artifacts
- execution receipts

For team use, the backend may run on a LAN/shared host.

Expected team endpoint:

```text
http://trident.local
```

Expected local endpoint:

```text
http://localhost
```

---

## 6. Project / Git Repository Model

A Trident project is a registered Git repository.

Minimum project record:

```text
project_id
workspace_id
repo_name
repo_root_path
git_remote_url
active_branch
allowed_root_path
index_status
lock_policy
created_at
updated_at
```

The backend tracks Git state and file locks for each project.

The IDE may open and edit files locally, but edits must be governed by backend lock and Git policy.

---

## 7. Team Collaboration Model

The backend enables multiple users/agents to work on a shared project without conflicting edits.

Required controls:

- workspace membership
- user identity
- project roles
- file locks
- task ownership
- branch awareness
- visible active users
- visible active agents
- audit history

---

## 8. File Locking from IDE

Before the IDE edits a governed file:

1. IDE requests lock from backend.
2. Backend validates:
   - project exists
   - file path is under allowed root
   - directive/task context exists
   - no conflicting lock exists
   - user/agent has permission
3. Backend grants or rejects lock.
4. IDE displays lock status.
5. Edit proceeds only if lock is granted.

No silent local write is allowed for governed Trident work.

---

## 9. Git Governance from IDE

The IDE must display backend-confirmed Git status:

- repo detected
- active branch
- dirty state
- staged changes
- diff available
- remote ahead/behind status
- commit requirement
- proof requirement

The IDE must not close a task directly.

Task closure occurs only through backend LangGraph state after proof review.

---

## 10. Cursor-Like Capabilities Required

The Trident IDE client must support:

- repo-aware chat
- selected-file context
- selected-code context
- inline edit suggestions
- apply patch workflow
- explain code
- generate tests
- fix errors
- ask about project architecture
- memory-aware answers
- agent workflow visibility

But unlike Cursor, all meaningful work must remain tied to:

- directives
- graph state
- memory writes
- proof objects
- Git/file lock governance

---

## 11. Agent Panel in IDE

The IDE must include a Trident Agent panel showing:

```text
Current Directive:
Current LangGraph Node:
Active Agent:
Task State:
Required Proof:
File Locks:
Git Status:
Router Decision:
Pending MCP Approvals:
```

Agents shown:

- Architect
- Engineer
- Reviewer
- Documentation

Agent actions must reflect backend LangGraph state.

---

## 12. Memory Panel in IDE

The IDE must expose project memory:

- architecture rules
- prior decisions
- coding standards
- known issues
- directive history
- handoff records
- proof history

The IDE may display retrieved memory snippets, but memory writes must occur through the backend.

---

## 13. Chat / Composer Behavior

The IDE chat/composer must support:

- selected code context
- selected file context
- project-wide context
- directive-bound requests
- “ask only”
- “propose patch”
- “request implementation”
- “send to reviewer”
- “update docs”

Every action must map to a backend task event.

---

## 14. Local-First Model Routing in IDE

IDE requests must flow through the backend router.

Rules:

- local LLM primary
- external LLM only for high-level reasoning or local insufficiency
- no silent external escalation
- token optimization before external calls
- routing decision visible in IDE

---

## 15. MCP Approvals in IDE

The IDE must display MCP execution requests:

```text
Command:
Target:
Risk:
Reason:
Approve / Reject / Modify
```

No command execution directly from IDE agent logic.

All execution goes through backend MCP.

---

## 16. Web Backend Relationship

The web backend provides:

- shared state
- project administration
- team view
- directive board
- full audit trail
- approval center
- proof review
- memory inspection

The IDE provides:

- coding surface
- local editing
- project navigation
- developer-facing agent interaction

Both must remain synchronized through backend APIs.

---

## 17. Code - OSS / VS Code Strategy

The first implementation should not immediately fork and deeply modify Code - OSS unless required.

Preferred sequence:

1. Build Trident IDE extension/client bridge for VS Code-compatible environment.
2. Validate backend integration.
3. Package controlled Trident IDE distribution.
4. Fork Code - OSS only if extension APIs cannot enforce required behavior.

Final product may be:

```text
Trident IDE
```

based on Code - OSS, with Trident extension preinstalled and configured.

---

## 18. Hard Constraints

Engineering must not:

- create a separate IDE-only memory system
- let the IDE bypass backend file locks
- let the IDE bypass backend Git governance
- let the IDE bypass LangGraph workflows
- let IDE agents call shell directly
- let IDE agents call external APIs directly
- treat local chat as ungoverned task execution
- close directives from the IDE without backend approval

---

## 19. Required Backend APIs for IDE

Minimum API categories:

```text
/project/register
/project/status
/git/status
/git/diff
/locks/acquire
/locks/release
/directives/create
/directives/status
/agents/state
/memory/query
/router/request
/mcp/requests
/mcp/approve
/proof/list
/proof/attach
```

Exact endpoint naming may differ, but all capabilities must exist.

---

## 20. Required IDE Components

Minimum IDE components:

```text
Trident Sidebar
Trident Chat Panel
Directive Panel
Agent Workflow Panel
Memory Panel
Git/Lock Status Panel
MCP Approval Panel
Proof Panel
Settings Panel
```

---

## 21. Acceptance Criteria

This architecture is accepted when:

- Trident is explicitly defined as both IDE client and web backend.
- Backend remains the shared source of truth.
- IDE behavior is governed by backend state.
- File locks are required for governed edits.
- Git state is visible and enforced.
- Agent workflows remain LangGraph-controlled.
- Local-first routing applies to IDE requests.
- MCP execution approvals are visible in IDE and web.

---

## 22. Manifest Link

Parent: Trident Manifest v1.0  
Depends on: 000A–000N  
Updates: 000H, 000J, 000K, 100H  
Unlocks: Implementation Directive 100K — Trident IDE Client Bootstrap

---

END OF DOCUMENT
