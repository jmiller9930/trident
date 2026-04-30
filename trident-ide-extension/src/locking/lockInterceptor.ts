import * as path from "path";
import * as vscode from "vscode";

/** Workspace-relative POSIX path for lock APIs, or null if not a governed workspace file. */
export function relativePathIfGoverned(doc: vscode.TextDocument): string | null {
  if (doc.isUntitled || doc.uri.scheme !== "file") {
    return null;
  }
  const wf = vscode.workspace.getWorkspaceFolder(doc.uri);
  if (!wf) {
    return null;
  }
  const rel = path.relative(wf.uri.fsPath, doc.uri.fsPath).split(path.sep).join("/");
  if (!rel || rel.startsWith("..") || path.isAbsolute(rel)) {
    return null;
  }
  return rel;
}
