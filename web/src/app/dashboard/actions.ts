"use server";

import { revalidatePath } from "next/cache";

import { apiFetch, type ApiKeyCreated, type Workspace } from "@/lib/api";

export type ActionResult<T = undefined> =
  | { ok: true; data: T }
  | { ok: false; error: string };

export async function createWorkspaceAction(
  name: string,
): Promise<ActionResult<Workspace>> {
  const trimmed = name.trim();
  if (!trimmed) return { ok: false, error: "Name is required" };

  const res = await apiFetch("/admin/workspaces", {
    method: "POST",
    body: JSON.stringify({ name: trimmed }),
  });
  if (!res.ok) return { ok: false, error: "Could not create workspace" };

  revalidatePath("/dashboard");
  return { ok: true, data: (await res.json()) as Workspace };
}

export async function issueKeyAction(
  workspaceId: string,
  name: string,
): Promise<ActionResult<ApiKeyCreated>> {
  const trimmed = name.trim();
  if (!trimmed) return { ok: false, error: "Name is required" };

  const res = await apiFetch(`/admin/workspaces/${workspaceId}/keys`, {
    method: "POST",
    body: JSON.stringify({ name: trimmed }),
  });
  if (!res.ok) return { ok: false, error: "Could not create API key" };

  revalidatePath(`/dashboard/workspaces/${workspaceId}`);
  return { ok: true, data: (await res.json()) as ApiKeyCreated };
}

export async function revokeKeyAction(
  workspaceId: string,
  keyId: string,
): Promise<ActionResult> {
  const res = await apiFetch(`/admin/workspaces/${workspaceId}/keys/${keyId}`, {
    method: "DELETE",
  });
  if (!res.ok) return { ok: false, error: "Could not revoke key" };

  revalidatePath(`/dashboard/workspaces/${workspaceId}`);
  return { ok: true, data: undefined };
}

export async function deleteDeploymentAction(
  workspaceId: string,
  deploymentId: string,
): Promise<ActionResult> {
  const res = await apiFetch(
    `/admin/workspaces/${workspaceId}/deployments/${deploymentId}`,
    { method: "DELETE" },
  );
  if (!res.ok) return { ok: false, error: "Could not delete deployment" };

  revalidatePath(`/dashboard/workspaces/${workspaceId}`);
  return { ok: true, data: undefined };
}
