# TRIDENT IMPLEMENTATION DIRECTIVE 100M
## IDE Patch + Apply Workflow (Cursor-Style Controlled Edits)

---

## 1. Purpose

Implement a Cursor-style patch generation and apply workflow inside the Trident IDE, ensuring that all code edits are proposed, reviewed, and applied through governed processes tied to file locks, Git context, and backend approval.

This directive enables safe, auditable code changes from IDE-driven agent interactions.

---

## 2. Scope

Covers:
- Patch generation (diff-based)
- Patch preview UI
- Apply / reject workflow
- Integration with file locks (**100P**)
- Integration with Git status (100E)
- Backend validation before apply
- Proof object generation for applied changes

---

## 3. Core Principle

> No code is modified directly.  
> All changes must be proposed as patches, reviewed, and then applied through a controlled workflow.

---

## 4. Patch Workflow

```text
User/Agent requests change
→ IDE sends request to backend
→ Backend returns proposed patch (diff)
→ IDE displays patch preview
→ User approves or rejects
→ If approved:
    → Validate file lock
    → Validate Git context
    → Apply patch
    → Generate proof objects
```

---

## 5. Required Components

```text
src/
  patch/
    patchClient.ts
    patchViewer.ts
    patchApplier.ts
    patchValidator.ts
```

---

## 6. Patch Format

Must use unified diff format:

```diff
--- a/file.py
+++ b/file.py
@@ -1,3 +1,4 @@
 old line
+new line
```

---

## 7. Patch Generation Rules

- Must include file path
- Must include diff context
- Must be scoped to allowed files
- Must not include unrelated changes

---

## 8. Patch Preview UI

Must display:
- file name
- diff view (add/remove)
- summary of changes
- associated directive
- associated agent

---

## 9. Apply Rules

Before applying:

System must:
- verify file lock (**100P**)
- verify Git repo state (100E)
- verify patch integrity
- verify directive context

---

## 10. Apply Behavior

- Apply patch to local file
- Capture resulting diff
- Store proof object
- Log audit event

---

## 11. Reject Behavior

- No file modification
- Log rejection
- Optionally request new patch

---

## 12. Git Integration

After apply:
- show updated diff
- mark file dirty
- require commit later (handled in future directive)

---

## 13. Hard Constraints

Engineering must NOT:
- allow direct editing bypassing patch workflow
- apply patch without validation
- apply patch without lock
- apply patch outside Git repo
- include hidden file changes

---

## 14. Required Tests

- patch generation test
- patch preview display test
- patch apply success test
- patch apply blocked without lock
- patch reject test

---

## 15. Proof Objects Required

- patch diff samples
- apply logs
- rejection logs
- before/after file snapshots

---

## 16. Acceptance Criteria

- all edits go through patch system
- patches are visible and reviewable
- apply requires validation
- proof objects created

---

## 17. Manifest Link

Parent: Trident Manifest v1.0  
Depends on: **100P**  
Unlocks: 100N — IDE Agent Workflow Integration

---

END OF DOCUMENT
