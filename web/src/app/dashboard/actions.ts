"use server";

import { revalidatePath } from "next/cache";

import {
  apiFetch,
  type AgentConnectResult,
  type ApiKeyCreated,
  type Workspace,
} from "@/lib/api";
import {
  isMockApiEnabled,
  mockConnectAgent,
  mockDeleteDeployment,
  mockRenewKey,
  mockUpdateWorkspaceSlug,
} from "@/lib/dev-mocks";

export type ActionResult<T = undefined> =
  | { ok: true; data: T }
  | { ok: false; error: string };

export async function connectAgentAction(): Promise<ActionResult<AgentConnectResult>> {
  if (isMockApiEnabled()) {
    const result = mockConnectAgent();
    revalidatePath("/dashboard");
    return { ok: true, data: result };
  }

  const res = await apiFetch("/admin/agents", { method: "POST" });
  if (!res.ok) return { ok: false, error: "Could not connect a new agent" };

  const result = (await res.json()) as AgentConnectResult;
  revalidatePath("/dashboard");
  revalidatePath(`/dashboard/workspaces/${result.workspace.id}`);
  return { ok: true, data: result };
}

export async function renewKeyAction(
  workspaceId: string,
): Promise<ActionResult<ApiKeyCreated>> {
  if (isMockApiEnabled()) {
    const key = mockRenewKey(workspaceId);
    revalidatePath(`/dashboard/workspaces/${workspaceId}`);
    return { ok: true, data: key };
  }

  const res = await apiFetch(`/admin/workspaces/${workspaceId}/keys/renew`, {
    method: "POST",
  });
  if (!res.ok) return { ok: false, error: "Could not renew the connection" };

  revalidatePath(`/dashboard/workspaces/${workspaceId}`);
  return { ok: true, data: (await res.json()) as ApiKeyCreated };
}

export async function updateWorkspaceSlugAction(
  workspaceId: string,
  slug: string,
): Promise<ActionResult<Workspace>> {
  const trimmed = slug.trim();
  if (!trimmed) return { ok: false, error: "Slug is required" };

  if (isMockApiEnabled()) {
    const result = mockUpdateWorkspaceSlug(workspaceId, trimmed);
    if (!result.ok) return result;
    revalidatePath("/dashboard");
    revalidatePath(`/dashboard/workspaces/${workspaceId}`);
    return result;
  }

  const res = await apiFetch(`/admin/workspaces/${workspaceId}`, {
    method: "PATCH",
    body: JSON.stringify({ slug: trimmed }),
  });
  if (res.status === 409) return { ok: false, error: "That slug is already taken" };
  if (res.status === 422) {
    return {
      ok: false,
      error: "Only lowercase letters, numbers, and hyphens are allowed",
    };
  }
  if (!res.ok) return { ok: false, error: "Could not update slug" };

  revalidatePath("/dashboard");
  revalidatePath(`/dashboard/workspaces/${workspaceId}`);
  return { ok: true, data: (await res.json()) as Workspace };
}

export async function deleteDeploymentAction(
  workspaceId: string,
  deploymentId: string,
): Promise<ActionResult> {
  if (isMockApiEnabled()) {
    if (!mockDeleteDeployment(workspaceId, deploymentId)) {
      return { ok: false, error: "Could not delete deployment" };
    }
    revalidatePath(`/dashboard/workspaces/${workspaceId}`);
    return { ok: true, data: undefined };
  }

  const res = await apiFetch(
    `/admin/workspaces/${workspaceId}/deployments/${deploymentId}`,
    { method: "DELETE" },
  );
  if (!res.ok) return { ok: false, error: "Could not delete deployment" };

  revalidatePath(`/dashboard/workspaces/${workspaceId}`);
  return { ok: true, data: undefined };
}
