# TRIDENT FIX DIRECTIVE 004
## Memory Consistency + Transaction Model

---

## 1. Purpose

Close the memory consistency gap by defining ordering, atomicity, and synchronization rules between structured memory, vector memory, task ledger, and audit events.

---

## 2. Problem

Structured database writes and vector indexing can happen at different times. If not controlled, agents may retrieve stale or contradictory memory.

---

## 3. Required Fix

Engineering must implement a memory transaction model.

Required behavior:

- Structured memory write is authoritative.
- Every memory write receives a monotonic memory sequence number.
- Vector indexing is asynchronous but tied to structured source record.
- Retrieval must identify whether vector index is current, stale, or rebuilding.
- Agents must be able to request authoritative structured state when vector state is stale.
- Memory writes must occur through LangGraph nodes only.

---

## 4. Required Memory States

```text
STRUCTURED_COMMITTED
VECTOR_PENDING
VECTOR_INDEXED
VECTOR_STALE
VECTOR_FAILED
```

---

## 5. Acceptance Criteria

- No memory write exists without audit event.
- Vector result can be traced to structured source record.
- Stale vector index state is visible.
- Agent retrieval does not silently trust stale memory.
- Memory ordering is deterministic.

---

## 6. Required Tests

- structured write commit test
- vector pending test
- vector indexing completion test
- stale vector detection test
- retrieval fallback to structured memory test
- restart recovery test

---

## 7. Proof Objects

Engineering must return:

- memory sequence logs
- vector indexing logs
- stale-memory proof
- retrieval trace proof
- audit event samples

---

## 8. Manifest Link

Parent: Trident Manifest v1.0  
Depends on: 000C, 100D  
Must be completed before: 100G, 100I

---

END OF DOCUMENT
