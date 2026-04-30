# TRIDENT DIRECTIVE 000E

## Git + File Lock Enforcement

------------------------------------------------------------------------

## 1. Purpose

Define strict Git governance and file locking mechanisms to ensure safe,
conflict-free multi-agent and multi-user collaboration.

------------------------------------------------------------------------

## 2. Scope

Covers: - Git repository validation - Branch tracking - File locking
system - Commit enforcement - Conflict prevention - Rollback capability

------------------------------------------------------------------------

## 3. Git Enforcement Rules

All project directories MUST: - Be initialized as Git repositories -
Have a valid branch checked out - Have remote tracking configured
(optional for local-only)

------------------------------------------------------------------------

### 3.1 Pre-Execution Checks

Before any file mutation: - Verify repository exists - Verify branch is
active - Verify working tree state (clean or known dirty state) - Verify
no conflicting locks exist

------------------------------------------------------------------------

### 3.2 Post-Execution Requirements

After file mutation: - Generate Git diff - Stage changes - Require
commit message - Validate commit completion

------------------------------------------------------------------------

### 3.3 Prohibited Actions

-   No direct file mutation outside Git tracking
-   No forced overwrite of locked files
-   No bypass of commit step

------------------------------------------------------------------------

## 4. File Locking System

### 4.1 Lock Acquisition

-   File lock must be acquired before modification
-   Lock tied to:
    -   Agent
    -   Task ID
    -   User

------------------------------------------------------------------------

### 4.2 Lock Visibility

System must display: - Locked files - Owning agent - Task association

------------------------------------------------------------------------

### 4.3 Lock Enforcement

-   Locked files are read-only to others
-   Only owning agent may modify
-   Override requires explicit approval + audit log

------------------------------------------------------------------------

### 4.4 Lock Release

Locks are released when: - Task completes - Agent hands off - Timeout or
failure recovery

------------------------------------------------------------------------

## 5. Conflict Prevention

System must: - Prevent simultaneous edits - Block conflicting writes -
Alert users to locked resources

------------------------------------------------------------------------

## 6. Rollback Requirements

System must support: - Reverting commits - Restoring previous file
states - Tracking change history

------------------------------------------------------------------------

## 7. Integration with LangGraph

-   File locks tied to active node
-   Lock lifecycle follows task lifecycle
-   Ownership enforced via graph state

------------------------------------------------------------------------

## 8. Acceptance Criteria

-   No concurrent file modification allowed
-   All changes tracked via Git
-   Lock system prevents conflicts
-   Rollback is functional

------------------------------------------------------------------------

## 9. Required Tests

-   Lock acquisition tests
-   Lock conflict tests
-   Git commit validation tests
-   Rollback tests

------------------------------------------------------------------------

## 10. Manifest Link

Parent: Trident Manifest v1.0\
Depends on: 000A, 000B, 000C, 000D\
Unlocks: 000F

------------------------------------------------------------------------

END OF DOCUMENT
