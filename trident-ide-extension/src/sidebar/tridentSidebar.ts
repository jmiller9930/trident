import * as vscode from "vscode";
import { TridentClient } from "../api/tridentClient";

const DIR_HEADER_ID = "trident-directives-header";

export class TridentSidebarProvider implements vscode.TreeDataProvider<SidebarNode> {
  private readonly _onDidChange = new vscode.EventEmitter<SidebarNode | undefined | void>();
  readonly onDidChangeTreeData = this._onDidChange.event;

  constructor(private readonly client: TridentClient) {}

  refresh(): void {
    this._onDidChange.fire();
  }

  getTreeItem(element: SidebarNode): vscode.TreeItem {
    return element;
  }

  async getChildren(element?: SidebarNode): Promise<SidebarNode[]> {
    if (!element) {
      const conn = await this.client.connectionLabel();
      const connItem = new vscode.TreeItem(conn.label, vscode.TreeItemCollapsibleState.None);
      connItem.id = "trident-connection";
      connItem.description = conn.detail;
      connItem.iconPath = new vscode.ThemeIcon(conn.label.includes("connected") ? "debug-start" : "error");

      const dirHeader = new vscode.TreeItem("Directives", vscode.TreeItemCollapsibleState.Collapsed);
      dirHeader.id = DIR_HEADER_ID;
      dirHeader.iconPath = new vscode.ThemeIcon("list-tree");

      const chatCmd = new vscode.TreeItem("Open chat…", vscode.TreeItemCollapsibleState.None);
      chatCmd.id = "trident-open-chat";
      chatCmd.iconPath = new vscode.ThemeIcon("comment");
      chatCmd.command = {
        command: "trident.openChat",
        title: "Open chat",
      };

      const agentCmd = new vscode.TreeItem("Agent state…", vscode.TreeItemCollapsibleState.None);
      agentCmd.id = "trident-agent-state";
      agentCmd.iconPath = new vscode.ThemeIcon("organization");
      agentCmd.command = {
        command: "trident.showAgentState",
        title: "Agent state",
      };

      const statusCmd = new vscode.TreeItem("Backend status…", vscode.TreeItemCollapsibleState.None);
      statusCmd.id = "trident-status";
      statusCmd.iconPath = new vscode.ThemeIcon("pulse");
      statusCmd.command = {
        command: "trident.showStatus",
        title: "Status",
      };

      return [connItem, dirHeader, chatCmd, agentCmd, statusCmd];
    }

    if (element.id === DIR_HEADER_ID) {
      try {
        const list = await this.client.listDirectives();
        return list.items.map((d) => {
          const it = new vscode.TreeItem(d.title, vscode.TreeItemCollapsibleState.None);
          it.id = `directive-${d.id}`;
          it.description = d.status;
          it.iconPath = new vscode.ThemeIcon("symbol-interface");
          it.command = {
            command: "trident.selectDirective",
            title: "Select directive",
            arguments: [d.id, d.title],
          };
          return it;
        });
      } catch (e) {
        const err = new vscode.TreeItem(
          `Failed to load directives`,
          vscode.TreeItemCollapsibleState.None
        );
        err.id = "trident-directives-error";
        err.description = e instanceof Error ? e.message : String(e);
        err.iconPath = new vscode.ThemeIcon("warning");
        return [err];
      }
    }

    return [];
  }

  getParent(): undefined {
    return undefined;
  }
}

type SidebarNode = vscode.TreeItem;
