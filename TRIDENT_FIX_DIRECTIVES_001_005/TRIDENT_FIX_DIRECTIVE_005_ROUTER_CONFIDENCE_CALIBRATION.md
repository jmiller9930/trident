# TRIDENT FIX DIRECTIVE 005
## Router Confidence Calibration + External Escalation Guard

---

## 1. Purpose

Close the router misclassification and token-cost risk by defining calibrated confidence, escalation controls, and external-call budgeting.

---

## 2. Problem

A naive confidence score can either escalate too often, wasting external tokens, or fail to escalate when higher reasoning is required.

---

## 3. Required Fix

Engineering must implement router confidence calibration and escalation guardrails.

Required behavior:

- Router records local model attempt result.
- Router assigns confidence using measurable signals, not arbitrary text.
- Escalation requires one or more explicit trigger reasons.
- External payload must pass token optimization before sending.
- External usage must be budget-aware and logged.
- User/admin policy can disable external escalation.

---

## 4. Required Escalation Reasons

```text
LOW_CONFIDENCE
INCOMPLETE_RESPONSE
HIGH_REASONING_REQUIRED
VALIDATION_REQUIRED
LOCAL_MODEL_UNAVAILABLE
CONTEXT_WINDOW_LIMIT
USER_APPROVED_ESCALATION
```

---

## 5. Required Confidence Signals

Engineering must evaluate and implement available signals such as:

- local model self-rating
- validator model score
- missing acceptance criteria
- test failure after local attempt
- parse/schema failure
- repeated local retry failure
- task complexity classification

---

## 6. Acceptance Criteria

- External calls are never silent.
- External calls always include reason.
- External payload is minimized.
- Router decision is visible in UI and audit logs.
- External escalation can be disabled by policy.

---

## 7. Required Tests

- local success no escalation
- low confidence escalation
- external disabled block
- payload minimization test
- routing log validation
- budget threshold warning test

---

## 8. Proof Objects

Engineering must return:

- router decision logs
- confidence scoring examples
- minimized prompt samples
- external blocked proof
- UI visibility proof

---

## 9. Manifest Link

Parent: Trident Manifest v1.0  
Depends on: **000G**, **100R** (Model Router implementation)  
Must be completed before: production **external LLM API** use  

**Note:** **100G** is the **subsystem** router and is **out of scope** for this fix; confidence calibration applies to **model** routing only.

---

END OF DOCUMENT
