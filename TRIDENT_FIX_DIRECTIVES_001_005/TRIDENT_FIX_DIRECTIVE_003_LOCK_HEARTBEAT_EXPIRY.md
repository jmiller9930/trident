# TRIDENT FIX DIRECTIVE 003
## Lock Heartbeat + Expiration System

---

## 1. Purpose

Close the lock robustness gap by defining heartbeat, expiration, recovery, and stale-lock behavior for multi-user and multi-agent editing.

---

## 2. Problem

Static locks can become stale if an IDE crashes, network drops, an agent fails, or a user abandons a task.

---

## 3. Required Fix

Engineering must implement lock heartbeat and expiration.

Required behavior:

- Each active lock has heartbeat timestamp.
- IDE refreshes lock heartbeat at configured interval.
- Backend marks lock stale after missed heartbeat threshold.
- Stale locks enter `STALE_PENDING_RECOVERY`.
- Recovery requires policy-based release or owner/user confirmation.
- All lock recovery actions are audited.

---

## 4. Required Lock States

```text
ACTIVE
STALE_PENDING_RECOVERY
EXPIRED
RELEASED
FORCE_RELEASED
CONFLICTED
```

---

## 5. Acceptance Criteria

- Active locks refresh automatically.
- Dead IDE sessions produce stale locks.
- Stale locks do not allow editing.
- Force release requires permission and audit.
- Lock state is visible in IDE and web UI.

---

## 6. Required Tests

- heartbeat refresh test
- missed heartbeat stale test
- stale lock blocks edit test
- owner recovery test
- admin force-release test
- conflict race test

---

## 7. Proof Objects

Engineering must return:

- heartbeat logs
- stale-lock logs
- force-release audit event
- UI screenshot of stale lock
- race-condition test output

---

## 8. Manifest Link

Parent: Trident Manifest v1.0  
Depends on: 000E, 100E, 100P  
Must be completed before: 100M, 100N

---

END OF DOCUMENT
