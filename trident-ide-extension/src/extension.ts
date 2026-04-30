import * as vscode from "vscode";
import { TridentClient } from "./api/tridentClient";
import { getApiBaseUrl } from "./utils/config";
import { openChatPanel } from "./panels/chatPanel";
import { TridentSidebarProvider } from "./sidebar/tridentSidebar";

export function activate(context: vscode.ExtensionContext): void {
  const client = new TridentClient(getApiBaseUrl());
  const sidebar = new TridentSidebarProvider(client);

  context.subscriptions.push(
    vscode.window.registerTreeDataProvider("trident.sidebar", sidebar),
    vscode.commands.registerCommand("trident.refresh", () => {
      getApiBaseUrl(); // read config
      sidebar.refresh();
    }),
    vscode.commands.registerCommand("trident.openChat", () => openChatPanel(context, client)),
    vscode.commands.registerCommand("trident.showAgentState", () => showAgentState(client)),
    vscode.commands.registerCommand("trident.showStatus", () => showStatus(client)),
    vscode.commands.registerCommand("trident.selectDirective", (id: string, title?: string) => {
      if (typeof id !== "string") {
        return;
      }
      void context.workspaceState.update("trident.selectedDirectiveId", id);
      void vscode.window.showInformationMessage(`Trident active directive: ${title ?? id}`);
    })
  );
}

async function showAgentState(client: TridentClient): Promise<void> {
  let list;
  try {
    list = await client.listDirectives();
  } catch (e) {
    void vscode.window.showErrorMessage(e instanceof Error ? e.message : String(e));
    return;
  }
  const pick = await vscode.window.showQuickPick(
    list.items.map((i) => ({ label: i.title, description: i.status, id: i.id })),
    { placeHolder: "Directive for agent / memory state" }
  );
  if (!pick || !("id" in pick)) {
    return;
  }
  const id = (pick as { id: string }).id;
  try {
    const [detail, memory] = await Promise.all([client.getDirective(id), client.getMemoryDirective(id)]);
    const doc = await vscode.workspace.openTextDocument({
      content: JSON.stringify({ directive_detail: detail, memory }, null, 2),
      language: "json",
    });
    await vscode.window.showTextDocument(doc, { preview: true });
  } catch (e) {
    void vscode.window.showErrorMessage(e instanceof Error ? e.message : String(e));
  }
}

async function showStatus(client: TridentClient): Promise<void> {
  const h = await client.health();
  const msg = h.ok
    ? `Trident API healthy (${h.status}). ${h.body}`
    : `Trident API check failed (${h.status}). ${h.body}`;
  void vscode.window.showInformationMessage(msg, { modal: false });
}

export function deactivate(): void {}
