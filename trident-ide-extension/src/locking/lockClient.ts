import { TridentClient } from "../api/tridentClient";

/** Thin facade for lock REST calls (100P layout). */
export class LockClient {
  constructor(private readonly api: TridentClient) {}

  getActive(projectId: string, relativeFilePath: string) {
    return this.api.getActiveLock(projectId, relativeFilePath);
  }

  acquire(params: {
    project_id: string;
    directive_id: string;
    agent_role: string;
    user_id: string;
    file_path: string;
  }) {
    return this.api.acquireLock(params);
  }

  release(params: {
    lock_id: string;
    project_id: string;
    directive_id: string;
    agent_role: string;
    user_id: string;
    file_path: string;
  }) {
    return this.api.releaseLock(params);
  }
}
