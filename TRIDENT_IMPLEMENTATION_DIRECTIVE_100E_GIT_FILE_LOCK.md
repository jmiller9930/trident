# TRIDENT IMPLEMENTATION DIRECTIVE 100E
## Git + File Lock Implementation (Enforced Mutation Control)

---

## 1. Purpose

Implement Git governance and file lock enforcement as defined in Directive 000E, ensuring all file mutations are controlled, auditable, and conflict-free across agents and users.

---

## 2. Scope

Covers:
- Git repository validation
- Branch + status tracking
- File lock acquisition + release
- Lock enforcement in write paths
- Diff generation
- Commit enforcement (stubbed, no auto-commit yet)
- Audit + proof integration

---

## 3. Core Principle

> No file may be modified without:
> (1) an active file lock and
> (2) a tracked Git context.

---

## 4. Required Components

### 4.1 Git Service

Create:

```text
backend/app/git/
  git_service.py
  git_status.py
  git_diff.py
  git_validation.py
```

Responsibilities:
- validate repo existence
- detect branch
- detect dirty state
- generate diff

---

### 4.2 File Lock Service

Create:

```text
backend/app/locks/
  lock_service.py
  lock_validator.py
```

Responsibilities:
- acquire lock
- validate lock ownership
- release lock
- enforce lock before mutation

---

## 5. Lock Acquisition Rules

- Must include:
  - directive_id
  - agent_role
  - user_id
  - file_path
- Stored in `file_locks` table
- Cannot acquire if already locked

---

## 6. Lock Enforcement

Before any write operation:

System must:
- check lock exists
- verify agent owns lock
- reject if invalid

---

## 7. Git Validation Rules

Before mutation:

System must:
- verify repo exists
- verify branch exists
- capture current status

After mutation (simulated in this phase):
- generate diff
- store diff as proof object

---

## 8. Mutation Simulation (IMPORTANT)

In this directive:

- DO NOT perform real file writes yet
- simulate mutation intent
- generate placeholder diff

---

## 9. Audit Requirements

Every operation must log:

- lock_created
- lock_rejected
- lock_released
- git_status_checked
- diff_generated

---

## 10. Hard Constraints

Engineering must NOT:
- modify files on disk yet
- auto-commit to Git
- bypass lock validation
- bypass Git validation

---

## 11. Required Tests

- lock acquisition test
- lock conflict test
- lock ownership enforcement test
- git repo validation test
- diff generation test
- restart persistence test

---

## 12. Proof Objects Required

- lock creation logs
- lock conflict logs
- git status output
- diff output
- restart persistence proof

---

## 13. Acceptance Criteria

- lock system prevents concurrent modification
- Git validation runs before mutation
- diff proof is generated
- lock lifecycle is correct
- no unauthorized writes occur

---

## 14. Manifest Link

Parent: Trident Manifest v1.0  
Depends on: 100D  
Unlocks: 100F — MCP Execution Implementation

---

END OF DOCUMENT
