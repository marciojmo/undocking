import "server-only";

import { cookies } from "next/headers";

import {
  isMockApiEnabled,
  mockGetCurrentUser,
  mockGetProviders,
  mockGetWorkspace,
  mockListApiKeys,
  mockListDeployments,
  mockListWorkspaces,
} from "@/lib/dev-mocks";

// The Next.js server calls the API directly (not through the browser proxy),
// forwarding the caller's session cookie so the backend can authenticate the
// request. Defaults to the local backend.
const API_BASE = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

export interface User {
  id: string;
  email: string;
  name: string;
}

export interface Workspace {
  id: string;
  slug: string;
  name: string;
  plan: string;
  created_at: string;
}

export interface ApiKey {
  id: string;
  name: string | null;
  key_prefix: string;
  created_at: string;
  revoked_at: string | null;
}

export interface ApiKeyCreated extends ApiKey {
  key: string;
}

export interface AgentConnectResult {
  workspace: Workspace;
  key: ApiKeyCreated;
}

export interface Deployment {
  id: string;
  slug: string;
  content_type: string;
  created_at: string;
  url: string;
}

/** Synthetic response when the backend is unreachable. */
function unavailableResponse(): Response {
  return new Response(null, { status: 503, statusText: "Service Unavailable" });
}

/** Calls the backend with the current request's cookies forwarded. */
export async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const cookieStore = await cookies();
  const headers = new Headers(init?.headers);
  headers.set("cookie", cookieStore.toString());
  if (init?.body && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }
  try {
    return await fetch(`${API_BASE}${path}`, { ...init, headers, cache: "no-store" });
  } catch {
    return unavailableResponse();
  }
}

async function getJson<T>(path: string): Promise<T> {
  const res = await apiFetch(path);
  if (!res.ok) {
    throw new Error(`GET ${path} failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

/** Returns the signed-in user, or null when the session is missing/expired. */
export async function getCurrentUser(): Promise<User | null> {
  if (isMockApiEnabled()) return mockGetCurrentUser();

  const res = await apiFetch("/auth/me");
  if (res.status === 401) return null;
  if (!res.ok) throw new Error(`GET /auth/me failed: ${res.status}`);
  return res.json() as Promise<User>;
}

export async function getProviders(): Promise<string[]> {
  if (isMockApiEnabled()) return mockGetProviders();

  const res = await apiFetch("/auth/providers");
  if (!res.ok) return [];
  const data = (await res.json()) as { providers: string[] };
  return data.providers;
}

export function listWorkspaces(): Promise<Workspace[]> {
  if (isMockApiEnabled()) return Promise.resolve(mockListWorkspaces());
  return getJson<Workspace[]>("/admin/workspaces");
}

/** Returns a workspace by id, or null when it isn't found / not owned. */
export async function getWorkspace(id: string): Promise<Workspace | null> {
  if (isMockApiEnabled()) return mockGetWorkspace(id);

  const res = await apiFetch(`/admin/workspaces/${id}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`GET workspace failed: ${res.status}`);
  return res.json() as Promise<Workspace>;
}

export function listApiKeys(workspaceId: string): Promise<ApiKey[]> {
  if (isMockApiEnabled()) return Promise.resolve(mockListApiKeys(workspaceId));
  return getJson<ApiKey[]>(`/admin/workspaces/${workspaceId}/keys`);
}

export function listDeployments(workspaceId: string): Promise<Deployment[]> {
  if (isMockApiEnabled()) return Promise.resolve(mockListDeployments(workspaceId));
  return getJson<Deployment[]>(`/admin/workspaces/${workspaceId}/deployments`);
}
