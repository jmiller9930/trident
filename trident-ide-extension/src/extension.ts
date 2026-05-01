import * as vscode from "vscode";
import { TridentClient } from "./api/tridentClient";
import { registerEditGuard } from "./editors/editGuard";
import { openChatPanel } from "./panels/chatPanel";
import { openTimelinePanel } from "./panels/timelinePanel";
import { openExecutionStatePanel } from "./panels/executionStatePanel";
import { registerPatchWorkflow } from "./patch/patchViewer";
import { TridentStatusBar } from "./statusBar/tridentStatusBar";
import { TridentSidebarProvider } from "./sidebar/tridentSidebar";
import { getApiBaseUrl, getGovernanceIdentity, humanStatus, isDebugMode, isUuid } from "./utils/config";

export function activate(context: vscode.ExtensionContext): void {
  const client = new TridentClient(getApiBaseUrl());
  const statusBar = new TridentStatusBar(context);
  const sidebar = new TridentSidebarProvider(client, context, statusBar);

  registerEditGuard(context, client);
  registerPatchWorkflow(context, client);

  context.subscriptions.push(
    vscode.window.registerTreeDataProvider("trident.sidebar", sidebar),

    vscode.commands.registerCommand("trident.refresh", () => sidebar.refresh()),

    vscode.commands.registerCommand("trident.openChat", () =>
      openChatPanel(context, client, statusBar)
    ),

    vscode.commands.registerCommand("trident.showTimeline", () =>
      openTimelinePanel(context, client, statusBar)
    ),

    vscode.commands.registerCommand("trident.showAgentState", () =>
      showAgentState(context, client)
    ),

    vscode.commands.registerCommand("trident.showStatus", () =>
      showStatus(client)
    ),

    vscode.commands.registerCommand("trident.selectDirective", (id: string, title?: string) => {
      if (typeof id !== "string") return;
      void context.workspaceState.update("trident.selectedDirectiveId", id);
      void context.workspaceState.update("trident.selectedDirectiveTitle", title ?? id);
      void vscode.window.showInformationMessage(`Trident: active task — ${title ?? id}`);
      sidebar.refresh();
    }),

    vscode.commands.registerCommand("trident.createWorkRequest", () =>
      createWorkRequest(context, client, statusBar)
    ),

    vscode.commands.registerCommand("trident.toggleDebugMode", () =>
      toggleDebugMode()
    ),

    vscode.commands.registerCommand("trident.acquireLock", () =>
      acquireLockForActiveFile(context, client, statusBar)
    ),

    vscode.commands.registerCommand("trident.releaseLock", () =>
      releaseLockCmd(context, client, statusBar)
    ),

    vscode.commands.registerCommand("trident.showExecutionState", () =>
      openExecutionStatePanel(context, client)
    )
  );
}

// ── createWorkRequest ────────────────────────────────────────────────────────

async function createWorkRequest(
  context: vscode.ExtensionContext,
  client: TridentClient,
  statusBar: TridentStatusBar
): Promise<void> {
  const identity = getGovernanceIdentity();
  if (!identity) {
    void vscode.window.showErrorMessage(
      "Trident: set trident.projectId and trident.userId first."
    );
    return;
  }
  const workspaceId = identity.workspaceId;
  if (!isUuid(workspaceId)) {
    void vscode.window.showErrorMessage(
      "Trident: set trident.workspaceId (UUID) to create a new task."
    );
    return;
  }

  const title = await vscode.window.showInputBox({
    prompt: "Describe the task",
    placeHolder: "e.g. Add input validation to login form",
    validateInput: (v) => (v.trim().length < 3 ? "Task description too short" : null),
  });
  if (!title) return;

  try {
    const resp = await client.createDirective({
      workspace_id: workspaceId,
      project_id: identity.projectId,
      title: title.trim(),
      graph_id: "trident-ide-002",
      created_by_user_id: identity.userId,
    });
    const directiveId = resp.directive.id;
    const directiveTitle = resp.directive.title;

    void context.workspaceState.update("trident.selectedDirectiveId", directiveId);
    void context.workspaceState.update("trident.selectedDirectiveTitle", directiveTitle);
    sidebar_refresh_pending = true;

    const action = await vscode.window.showInformationMessage(
      `Task created: "${directiveTitle}"`,
      "Run workflow",
      "Open chat",
      "View progress"
    );

    if (action === "Run workflow") {
      const res = await client.postIdeAction({
        project_id: identity.projectId,
        directive_id: directiveId,
        agent_role: identity.agentRole,
        action: "RUN_WORKFLOW",
        actor_id: "vscode-trident-extension",
      });
      void vscode.window.showInformationMessage(
        `Workflow complete: ${humanStatus(res.directive_status)}`
      );
      const s = await client.getIdeStatus(directiveId);
      statusBar.updateFromIdeStatus(s);
      await openTimelinePanel(context, client, statusBar);
    } else if (action === "Open chat") {
      await openChatPanel(context, client, statusBar);
    } else if (action === "View progress") {
      await openTimelinePanel(context, client, statusBar);
    }
  } catch (e) {
    void vscode.window.showErrorMessage(
      `Trident: failed to create task — ${e instanceof Error ? e.message : String(e)}`
    );
  }
}

let sidebar_refresh_pending = false;

// ── showAgentState ───────────────────────────────────────────────────────────

async function showAgentState(
  context: vscode.ExtensionContext,
  client: TridentClient
): Promise<void> {
  const debug = isDebugMode();
  let directiveId = context.workspaceState.get<string>("trident.selectedDirectiveId");
  if (!directiveId) {
    const list = await client.listDirectives();
    const pick = await vscode.window.showQuickPick(
      list.items.map((i) => ({ label: i.title, description: humanStatus(i.status), id: i.id })),
      { placeHolder: "Select task to inspect" }
    );
    if (!pick || !("id" in pick)) return;
    directiveId = (pick as { id: string }).id;
  }
  try {
    if (debug) {
      const [detail, memory] = await Promise.all([
        client.getDirective(directiveId),
        client.getMemoryDirective(directiveId),
      ]);
      const doc = await vscode.workspace.openTextDocument({
        content: JSON.stringify({ directive_detail: detail, memory }, null, 2),
        language: "json",
      });
      await vscode.window.showTextDocument(doc, { preview: true });
    } else {
      const summary = await client.getIdeProofSummary(directiveId);
      const doc = await vscode.workspace.openTextDocument({
        content: [
          `Task:   ${summary.title}`,
          `Status: ${humanStatus(summary.directive_status)}`,
          `Ledger: ${summary.ledger_state}`,
          `Agent:  ${summary.current_agent_role}`,
          `Proofs: ${summary.proof_count}`,
          summary.last_routing_model ? `Last model: ${summary.last_routing_model}` : null,
          summary.last_patch_event?.file_path
            ? `Last patch: ${String(summary.last_patch_event.file_path)}`
            : null,
        ]
          .filter(Boolean)
          .join("\n"),
        language: "plaintext",
      });
      await vscode.window.showTextDocument(doc, { preview: true });
    }
  } catch (e) {
    void vscode.window.showErrorMessage(e instanceof Error ? e.message : String(e));
  }
}

// ── showStatus ───────────────────────────────────────────────────────────────

async function showStatus(client: TridentClient): Promise<void> {
  const h = await client.health();
  const msg = h.ok
    ? `Trident API healthy (${h.status}).`
    : `Trident API check failed (${h.status}). ${h.body}`;
  void vscode.window.showInformationMessage(msg, { modal: false });
}

// ── toggleDebugMode ──────────────────────────────────────────────────────────

async function toggleDebugMode(): Promise<void> {
  const conf = vscode.workspace.getConfiguration("trident");
  const current = conf.get<boolean>("debugMode") ?? false;
  await conf.update("debugMode", !current, vscode.ConfigurationTarget.Global);
  void vscode.window.showInformationMessage(
    `Trident debug mode: ${!current ? "ON" : "OFF"}`
  );
}

// ── lock helpers ──────────────────────────────────────────────────────────────

async function acquireLockForActiveFile(
  context: vscode.ExtensionContext,
  client: TridentClient,
  statusBar: TridentStatusBar
): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  const id = getGovernanceIdentity();
  const dir = context.workspaceState.get<string>("trident.selectedDirectiveId");
  if (!editor || !id || !dir) {
    void vscode.window.showErrorMessage("Trident: set projectId, userId, select a task, open a file.");
    return;
  }
  const ws = vscode.workspace.getWorkspaceFolder(editor.document.uri);
  if (!ws) {
    void vscode.window.showErrorMessage("Trident: active file must be in a workspace folder.");
    return;
  }
  const rel = vscode.workspace.asRelativePath(editor.document.uri, false);
  try {
    const lock = await client.acquireLock({
      project_id: id.projectId,
      directive_id: dir,
      agent_role: id.agentRole,
      user_id: id.userId,
      file_path: rel,
    });
    statusBar.showLock(lock.lock_id, rel);
    void vscode.window.showInformationMessage(`Trident: lock acquired for ${rel}`);
  } catch (e) {
    void vscode.window.showErrorMessage(e instanceof Error ? e.message : String(e));
  }
}

async function releaseLockCmd(
  context: vscode.ExtensionContext,
  client: TridentClient,
  statusBar: TridentStatusBar
): Promise<void> {
  const lockId = statusBar.currentLockId;
  const lockFile = statusBar.currentLockFile;
  const id = getGovernanceIdentity();
  const dir = context.workspaceState.get<string>("trident.selectedDirectiveId");
  if (!lockId || !lockFile || !id || !dir) {
    void vscode.window.showInformationMessage("Trident: no active lock to release.");
    return;
  }
  try {
    await client.releaseLock({
      lock_id: lockId,
      project_id: id.projectId,
      directive_id: dir,
      agent_role: id.agentRole,
      user_id: id.userId,
      file_path: lockFile,
    });
    statusBar.clearLock();
    void vscode.window.showInformationMessage(`Trident: lock released for ${lockFile}`);
  } catch (e) {
    void vscode.window.showErrorMessage(e instanceof Error ? e.message : String(e));
  }
}

export function deactivate(): void {}
