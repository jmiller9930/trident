# TRIDENT IMPLEMENTATION DIRECTIVE 100K
## Trident IDE Client Bootstrap (VS Code / Code - OSS Extension)

---

## 1. Purpose

Initialize the Trident IDE client as a VS Code / Code - OSS compatible extension that connects to the Trident backend and displays real system state.

This directive creates the first working IDE integration layer without implementing full editing enforcement or deep agent automation.

---

## 2. Scope

Covers:
- VS Code extension scaffold
- Backend connection
- Trident sidebar UI
- Directive panel (read-only)
- Chat panel (backend-driven)
- Agent state panel
- Git/lock status display (read-only)
- Basic configuration

---

## 3. Core Principle

> The IDE is a client of the Trident backend.  
> It must not contain independent logic or bypass backend governance.

---

## 4. Extension Structure

```text
trident-ide-extension/
  package.json
  src/
    extension.ts
    api/
      tridentClient.ts
    panels/
      chatPanel.ts
      directivePanel.ts
      agentPanel.ts
      statusPanel.ts
    sidebar/
      tridentSidebar.ts
    utils/
      config.ts
  media/
  README.md
```

---

## 5. Required Capabilities

### 5.1 Backend Connection

- Configurable API URL:
```text
TRIDENT_API_URL=http://localhost:8000
```

- Must support:
  - connect
  - reconnect
  - health check

---

### 5.2 Sidebar

Must display:

- Active project
- Active directive
- Agent state
- Backend connection status

---

### 5.3 Chat Panel

- Sends prompt to backend
- Displays response
- No local LLM calls
- No direct external API calls

---

### 5.4 Directive Panel

- Lists directives
- Shows status
- Read-only in this phase

---

### 5.5 Agent Panel

Displays:

- current agent
- current LangGraph node
- directive state

---

### 5.6 Status Panel

Displays:

- Git status (via backend)
- file lock info (via backend)
- router decision (last request)

---

## 6. Hard Constraints

Engineering must NOT:

- call local LLM directly
- call external APIs directly
- modify files
- bypass backend APIs
- simulate backend data

---

## 7. Required Tests

- extension loads
- connects to backend
- displays directives
- displays agent state
- chat panel sends/receives data

---

## 8. Proof Objects Required

- extension install proof
- backend connection logs
- UI screenshots
- API response samples

---

## 9. Acceptance Criteria

- extension runs in VS Code / Code OSS
- backend connection works
- UI reflects real backend data
- no local logic bypass

---

## 10. Manifest Link

Parent: Trident Manifest v1.0  
Depends on: 000O, 100H  
Unlocks: 100L — IDE File Lock + Governed Edit Flow

---

END OF DOCUMENT
