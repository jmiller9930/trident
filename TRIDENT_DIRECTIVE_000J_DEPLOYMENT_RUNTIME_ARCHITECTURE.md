# TRIDENT DIRECTIVE 000J

## Deployment + Runtime Architecture

------------------------------------------------------------------------

## 1. Purpose

Define the deployment model, runtime services, persistence layout,
networking boundaries, and operational requirements for running Trident
as a local-first, team-capable AI control plane.

------------------------------------------------------------------------

## 2. Scope

Covers: - Containerized runtime architecture - Service layout - Local vs
LAN/team deployment - Persistent storage - Secrets handling - Model
runtime placement - Network boundaries - Health checks - Backup and
restore - Operational validation

------------------------------------------------------------------------

## 3. Core Principle

> Trident must run as a containerized web-based control plane while
> remaining local-first, private, auditable, and capable of team
> collaboration.

------------------------------------------------------------------------

## 4. Runtime Deployment Modes

### 4.1 Single-User Local Mode

Trident may run locally on the user's workstation.

Expected access pattern:

``` text
http://localhost
```

Use cases: - individual developer workflow - local project indexing -
local model execution - local MCP approval testing

------------------------------------------------------------------------

### 4.2 Team / LAN Mode

Trident may run on an approved LAN-accessible host.

Expected access pattern:

``` text
http://trident.local
```

Use cases: - multi-user collaboration - shared project workspaces -
centralized task ledger - shared memory - shared execution governance

------------------------------------------------------------------------

## 5. Required Services

### 5.1 trident-web

Responsibilities: - Browser UI - Directive workspace - Agent workflow
visualization - Git status display - Memory inspection - Approval panels

------------------------------------------------------------------------

### 5.2 trident-api

Responsibilities: - Primary backend API - OpenAI-compatible endpoint -
LangGraph workflow coordination - Router invocation - Auth/session
interface - UI state API

------------------------------------------------------------------------

### 5.3 trident-worker

Responsibilities: - Background indexing - Long-running jobs - Memory
maintenance - Document ingestion - Async proof collection

------------------------------------------------------------------------

### 5.4 trident-db

Responsibilities: - Task ledger - Users/workspaces - File locks - Agent
handoffs - Proof object metadata - Audit log metadata

Recommended backend: - PostgreSQL

------------------------------------------------------------------------

### 5.5 trident-vector

Responsibilities: - Semantic memory retrieval - Document/code
embeddings - Project context indexing

Recommended backend: - ChromaDB initially - Qdrant optional later if
scale requires

------------------------------------------------------------------------

### 5.6 trident-exec

Responsibilities: - MCP execution broker - SSH adapter - vCenter
adapter - Docker/runtime adapter - Command classification - Execution
receipt capture

------------------------------------------------------------------------

### 5.7 model-runtime

Responsibilities: - Local LLM hosting - Embedding model hosting -
Optional model adapters

Allowed implementations: - Ollama - llama.cpp - MLX - other local model
backends through adapters

Model runtime may run: - inside container - on host - on dedicated LAN
inference node

------------------------------------------------------------------------

## 6. Container Boundary Rules

Each service must have a clear responsibility.

No service may: - bypass the task ledger - mutate memory directly
outside approved paths - execute commands outside MCP - perform hidden
external API calls - bypass LangGraph workflow state

------------------------------------------------------------------------

## 7. Persistence Requirements

Persistent volumes required for:

``` text
postgres_data/
vector_data/
project_indexes/
uploaded_documents/
execution_logs/
audit_logs/
proof_artifacts/
model_cache/
```

Persistence must survive: - container restart - host reboot -
application upgrade

------------------------------------------------------------------------

## 8. Network Architecture

### 8.1 Internal Network

Services communicate on a private Docker network.

Example:

``` text
trident-web     → trident-api
trident-api     → trident-db
trident-api     → trident-vector
trident-api     → trident-exec
trident-worker  → trident-db / trident-vector
trident-exec    → approved SSH/API targets
```

------------------------------------------------------------------------

### 8.2 External Network Access

External access is restricted to: - approved external LLM APIs -
approved MCP targets - approved package/model sources - approved Git
remotes

All external calls must be logged.

------------------------------------------------------------------------

## 9. Secrets Handling

Secrets include: - external API keys - SSH keys - vCenter credentials -
database credentials - model provider tokens

Rules: - no plaintext secrets in logs - no secrets committed to Git -
secrets mounted through secure environment or secret store - access
scoped by service - secret use audited

------------------------------------------------------------------------

## 10. Local Model Runtime Policy

Local model is primary.

The runtime must support: - local coding model - local embedding model -
model health checks - model availability reporting - fallback status
reporting

Failure of local model must: - be logged - update router state -
optionally trigger external escalation if policy allows

------------------------------------------------------------------------

## 11. External API Runtime Policy

External API is escalation only.

System must: - log reason for escalation - minimize payload - record
provider/model used - record token/cost metadata when available - attach
response to task memory

No silent external call is allowed.

------------------------------------------------------------------------

## 12. Health Checks

Required health checks:

``` text
/api/health
/api/ready
/api/version
/api/workflow/health
/api/memory/health
/api/router/health
/api/mcp/health
```

Each service must expose or report: - running status - dependency
status - version - last error - degraded mode if applicable

------------------------------------------------------------------------

## 13. Backup and Restore

Backup must include: - database - vector store - uploaded documents -
proof artifacts - audit logs - configuration excluding secrets -
manifest and directives

Restore test required before production use.

------------------------------------------------------------------------

## 14. Observability

System must provide: - structured logs - audit events - task timeline -
agent transition history - MCP execution receipts - router decisions -
memory read/write traces - Git/file-lock events

------------------------------------------------------------------------

## 15. Upgrade Requirements

Upgrades must: - preserve data - run migrations explicitly - validate
schema compatibility - preserve manifest chain - preserve directive
history - include rollback instructions

------------------------------------------------------------------------

## 16. Runtime Security Rules

-   Authentication required for team mode
-   Role-based access enforced
-   Approved project roots only
-   Approved execution targets only
-   No unrestricted filesystem access
-   No unrestricted shell access
-   No direct LLM-to-shell path
-   No task closure without proof

------------------------------------------------------------------------

## 17. Deployment Acceptance Criteria

Deployment is acceptable only when:

-   all containers start successfully
-   UI is reachable
-   API health passes
-   database is persistent
-   vector memory is persistent
-   local model health is visible
-   MCP execution broker is reachable
-   Git/file-lock service is functional
-   LangGraph workflow can execute a test directive
-   router can perform local routing
-   external escalation is blocked or allowed according to policy
-   audit logging captures all major actions

------------------------------------------------------------------------

## 18. Required Tests

Engineering must provide:

### 18.1 Container Startup Test

Validate all services start and remain healthy.

### 18.2 Persistence Test

Restart containers and confirm task ledger, memory, uploads, and logs
survive.

### 18.3 Network Isolation Test

Confirm services communicate only through approved paths.

### 18.4 Local Model Test

Confirm local model can answer a basic coding prompt through the router.

### 18.5 External Escalation Test

Confirm external call requires policy approval and is logged.

### 18.6 MCP Execution Test

Confirm command execution routes through MCP and generates receipt.

### 18.7 LangGraph Runtime Test

Confirm test directive executes through graph state only.

### 18.8 UI Health Test

Confirm UI displays real backend state, not mock state.

### 18.9 Backup/Restore Test

Confirm a backup can be restored into a clean runtime.

------------------------------------------------------------------------

## 19. Proof Objects Required

Engineering must return:

``` text
docker compose ps output
health endpoint output
database persistence proof
vector persistence proof
LangGraph test directive proof
router decision log proof
MCP execution receipt proof
UI screenshot or UI state proof
backup/restore proof
git commit hash
```

------------------------------------------------------------------------

## 20. Manifest Link

Parent: Trident Manifest v1.0\
Depends on: 000A--000I\
Unlocks: Engineering Implementation Planning

------------------------------------------------------------------------

END OF DOCUMENT
