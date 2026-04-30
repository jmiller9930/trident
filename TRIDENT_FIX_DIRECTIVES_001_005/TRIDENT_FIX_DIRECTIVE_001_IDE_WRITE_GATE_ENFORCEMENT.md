# TRIDENT FIX DIRECTIVE 001
## IDE Write Gate Enforcement Layer

---

## 1. Purpose

Close the IDE enforcement gap identified in the adversarial review by requiring all governed file writes from the Trident IDE to pass through a write gate.

---

## 2. Problem

VS Code / Code - OSS can write directly to local files. If Trident relies only on backend file locks but does not intercept writes, users or extensions may bypass governance.

---

## 3. Required Fix

Engineering must implement an IDE Write Gate that intercepts governed file edits and prevents uncontrolled writes.

Required behavior:

- Detect whether a file belongs to a registered Trident project.
- Check whether the current edit is tied to an active directive.
- Require an active backend lock before allowing modification.
- Block edits when lock is missing, expired, owned by another user/agent, or not associated with the active directive.
- Log every allowed and blocked write attempt.

---

## 4. Required Design Decision

Engineering must evaluate and document the enforcement method:

1. VS Code extension-level document change interception
2. Custom file system provider / virtual workspace
3. Controlled Code - OSS distribution with stricter write policy
4. Hybrid approach

The chosen approach must explain residual bypass risk.

---

## 5. Acceptance Criteria

- Governed files cannot be modified through the IDE without a valid backend lock.
- Blocked writes are visible to the user.
- All write attempts are audited.
- The system clearly documents what cannot be technically prevented at OS level.

---

## 6. Required Tests

- Edit without lock is blocked.
- Edit with valid lock is allowed.
- Edit after lock expiry is blocked.
- Edit by wrong user/agent is blocked.
- Non-governed files are not incorrectly blocked.

---

## 7. Proof Objects

Engineering must return:

- write gate test logs
- blocked edit screenshot
- allowed edit screenshot
- audit event samples
- bypass-risk assessment

---

## 8. Manifest Link

Parent: Trident Manifest v1.0  
Depends on: 000O, 100K, 100P  
Must be completed before: 100M, 100N

---

END OF DOCUMENT
