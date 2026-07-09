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
  mockBulkDeleteDeployments,
  mockConnectAgent,
  mockDeleteDeployment,
  mockDeleteWorkspace,
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

export async function bulkDeleteDeploymentsAction(
  workspaceId: string,
  deploymentIds: string[],
): Promise<ActionResult<{ deletedIds: string[] }>> {
  if (deploymentIds.length === 0) return { ok: true, data: { deletedIds: [] } };

  if (isMockApiEnabled()) {
    const deletedIds = mockBulkDeleteDeployments(workspaceId, deploymentIds);
    revalidatePath(`/dashboard/workspaces/${workspaceId}`);
    return { ok: true, data: { deletedIds } };
  }

  const res = await apiFetch(
    `/admin/workspaces/${workspaceId}/deployments/bulk-delete`,
    {
      method: "POST",
      body: JSON.stringify({ deployment_ids: deploymentIds }),
    },
  );
  if (!res.ok) return { ok: false, error: "Could not delete deployments" };

  const body = (await res.json()) as { deleted_ids: string[] };
  revalidatePath(`/dashboard/workspaces/${workspaceId}`);
  return { ok: true, data: { deletedIds: body.deleted_ids } };
}

export async function deleteWorkspaceAction(
  workspaceId: string,
): Promise<ActionResult> {
  if (isMockApiEnabled()) {
    const result = mockDeleteWorkspace(workspaceId);
    if (!result.ok) return result;
    revalidatePath("/dashboard");
    return { ok: true, data: undefined };
  }

  const res = await apiFetch(`/admin/workspaces/${workspaceId}`, {
    method: "DELETE",
  });
  if (res.status === 409) {
    return { ok: false, error: "Delete all deployments before deleting this agent" };
  }
  if (!res.ok) return { ok: false, error: "Could not delete this agent" };

  revalidatePath("/dashboard");
  return { ok: true, data: undefined };
}
