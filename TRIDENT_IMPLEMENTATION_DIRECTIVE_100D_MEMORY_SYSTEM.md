# TRIDENT IMPLEMENTATION DIRECTIVE 100D
## Memory System Implementation (Shared + Persistent + Agent-Aware)

---

## 1. Purpose

Implement the full shared memory system defined in Directive 000C, enabling all agents to read/write structured and vector memory through LangGraph-controlled execution.

---

## 2. Scope

Covers:
- Structured memory (task, handoff, proof, decisions)
- Vector memory (semantic retrieval)
- Memory APIs
- Memory write enforcement
- Memory read enforcement
- Indexing + retrieval
- Audit logging for memory operations

---

## 3. Core Principle

> Memory is the shared source of truth across all agents.  
> All reads and writes must occur inside LangGraph execution.

---

## 4. Memory Types

### 4.1 Structured Memory
Stored in PostgreSQL:
- directives
- task ledger
- handoffs
- proof objects
- audit events

---

### 4.2 Vector Memory
Stored in ChromaDB (or equivalent):
- document embeddings
- code embeddings
- semantic search index

---

## 5. Required Components

### 5.1 Memory Service Layer

Create:

```text
backend/app/memory/
  memory_service.py
  memory_reader.py
  memory_writer.py
  vector_service.py
```

---

### 5.2 Memory APIs

```text
GET /api/v1/memory/project/{project_id}
GET /api/v1/memory/directive/{directive_id}
POST /api/v1/memory/write
```

---

## 6. Write Rules

Memory writes MUST:
- occur inside LangGraph node
- include task_id
- include agent_role
- create audit event
- validate schema

---

## 7. Read Rules

Memory reads MUST:
- be scoped to project or directive
- filter irrelevant data
- log access event

---

## 8. Vector Retrieval

Must support:
- similarity search
- top-k results
- context filtering
- fast lookup (<200ms target)

---

## 9. Persistence Requirements

- Memory survives restart
- Vector index persists
- Structured memory persists

---

## 10. Hard Constraints

Engineering must NOT:
- Allow direct memory mutation outside graph
- Bypass audit logging
- Mix structured + vector data improperly
- Store secrets in memory

---

## 11. Required Tests

- Memory write/read consistency
- Vector retrieval accuracy
- Multi-agent read/write test
- Restart persistence test

---

## 12. Proof Objects Required

- Memory write logs
- Retrieval logs
- Vector query output
- Restart persistence proof

---

## 13. Acceptance Criteria

- Memory is shared across agents
- Memory persists
- Reads/writes enforced through graph
- Retrieval is accurate and fast

---

## 14. Manifest Link

Parent: Trident Manifest v1.0  
Depends on: 100C  
Unlocks: 100E — Git + File Lock Implementation

---

END OF DOCUMENT
