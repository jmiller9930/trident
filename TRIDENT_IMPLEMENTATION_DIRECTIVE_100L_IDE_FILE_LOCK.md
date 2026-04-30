# TRIDENT IMPLEMENTATION DIRECTIVE 100L
## IDE File Lock + Governed Edit Flow

---

## 1. Purpose

Implement enforced file editing behavior inside the Trident IDE so that all file modifications are governed by backend file locks and Git validation.

This directive ensures the IDE cannot perform uncontrolled edits.

---

## 2. Scope

Covers:
- File open interception
- File edit interception
- Lock acquisition before edit
- Lock validation during edit
- Lock release after task
- Edit blocking when lock not granted
- UI feedback for lock state

---

## 3. Core Principle

> No file may be edited in the IDE unless a valid lock is granted by the Trident backend.

---

## 4. Required Flow

```text
User attempts to edit file
→ IDE requests lock from backend
→ Backend validates
→ Lock granted or rejected
→ If granted → editing allowed
→ If rejected → editing blocked
```

---

## 5. Required Components

```text
src/
  locking/
    lockClient.ts
    lockInterceptor.ts
  editors/
    editGuard.ts
```

---

## 6. Lock Acquisition

Must include:
- project_id
- directive_id
- file_path
- user_id

---

## 7. Lock Enforcement

During editing:
- verify lock ownership
- prevent edits if lock lost
- auto-refresh lock state

---

## 8. UI Behavior

IDE must show:
- file lock icon
- lock owner
- lock status
- rejection message if blocked

---

## 9. Git Awareness

IDE must:
- show file diff status
- warn on dirty state
- display branch

---

## 10. Hard Constraints

Engineering must NOT:
- allow editing without lock
- bypass backend validation
- store lock locally only
- allow silent overwrite

---

## 11. Required Tests

- edit blocked without lock
- edit allowed with lock
- lock conflict handling
- lock expiration handling

---

## 12. Proof Objects Required

- lock request logs
- edit block screenshots
- edit allowed screenshots
- conflict logs

---

## 13. Acceptance Criteria

- edits require lock
- conflicts prevented
- UI reflects lock state
- backend is source of truth

---

## 14. Manifest Link

Parent: Trident Manifest v1.0  
Depends on: 100K  
Unlocks: 100M — IDE Patch + Apply Workflow

---

END OF DOCUMENT
