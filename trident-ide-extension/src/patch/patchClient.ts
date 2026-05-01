import { TridentClient } from "../api/tridentClient";

export type PatchIdentity = {
  project_id: string;
  directive_id: string;
  agent_role: string;
  user_id: string;
  file_path: string;
};

/** 100M REST facade. */
export class PatchClient {
  constructor(private readonly api: TridentClient) {}

  propose(
    body: PatchIdentity & { before_text: string; after_text: string; correlation_id?: string | null }
  ): ReturnType<TridentClient["proposePatch"]> {
    return this.api.proposePatch(body);
  }

  reject(
    body: PatchIdentity & { reason?: string | null; correlation_id?: string | null }
  ): ReturnType<TridentClient["rejectPatch"]> {
    return this.api.rejectPatch(body);
  }

  applyComplete(
    body: PatchIdentity & {
      unified_diff: string;
      after_text: string;
      correlation_id?: string | null;
    }
  ): ReturnType<TridentClient["applyCompletePatch"]> {
    return this.api.applyCompletePatch(body);
  }
}
