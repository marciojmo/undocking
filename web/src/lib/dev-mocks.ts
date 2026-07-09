import type {
  AgentConnectResult,
  ApiKey,
  ApiKeyCreated,
  Deployment,
  User,
  Workspace,
} from "@/lib/api";

export function isMockApiEnabled(): boolean {
  return (
    process.env.DEV_MOCK_API === "true" &&
    process.env.NODE_ENV === "development"
  );
}

const MOCK_USER: User = {
  id: "00000000-0000-4000-8000-000000000001",
  email: "dev@ship.local",
  name: "Dev User",
};

const WORKSPACE_A_ID = "00000000-0000-4000-8000-000000000010";
const WORKSPACE_B_ID = "00000000-0000-4000-8000-000000000011";
const KEY_A_ID = "00000000-0000-4000-8000-000000000020";
const KEY_B_ID = "00000000-0000-4000-8000-000000000021";
const DEPLOY_A_ID = "00000000-0000-4000-8000-000000000030";
const DEPLOY_B_ID = "00000000-0000-4000-8000-000000000031";

const store = {
  workspaces: [
    {
      id: WORKSPACE_A_ID,
      slug: "demo",
      name: "Demo Workspace",
      plan: "free",
      created_at: "2026-01-15T10:00:00.000Z",
    },
    {
      id: WORKSPACE_B_ID,
      slug: "staging",
      name: "Staging",
      plan: "free",
      created_at: "2026-02-01T14:30:00.000Z",
    },
  ] as Workspace[],
  keys: {
    [WORKSPACE_A_ID]: [
      {
        id: KEY_A_ID,
        name: "Local agent",
        key_prefix: "sk_live_demo123456",
        created_at: "2026-01-20T09:00:00.000Z",
        revoked_at: null,
      },
    ],
    [WORKSPACE_B_ID]: [
      {
        id: KEY_B_ID,
        name: "CI",
        key_prefix: "sk_live_staging7890",
        created_at: "2026-02-05T11:00:00.000Z",
        revoked_at: null,
      },
    ],
  } as Record<string, ApiKey[]>,
  deployments: {
    [WORKSPACE_A_ID]: [
      {
        id: DEPLOY_A_ID,
        slug: "hello-world",
        content_type: "markdown",
        created_at: "2026-01-22T16:00:00.000Z",
        url: "http://localhost:8000/demo/hello-world",
      },
    ],
    [WORKSPACE_B_ID]: [
      {
        id: DEPLOY_B_ID,
        slug: "report",
        content_type: "html",
        created_at: "2026-02-10T08:00:00.000Z",
        url: "http://localhost:8000/staging/report",
      },
    ],
  } as Record<string, Deployment[]>,
};

function slugify(name: string): string {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 48) || "workspace";
}

function uniqueSlug(base: string, excludeId?: string): string {
  const existing = new Set(
    store.workspaces.filter((w) => w.id !== excludeId).map((w) => w.slug),
  );
  if (!existing.has(base)) return base;
  let n = 2;
  while (existing.has(`${base}-${n}`)) n++;
  return `${base}-${n}`;
}

function randomSlug(): string {
  return Array.from(crypto.getRandomValues(new Uint8Array(10)))
    .map((b) => (b % 36).toString(36))
    .join("");
}

const SLUG_PATTERN = /^[a-z0-9]+(-[a-z0-9]+)*$/;

function randomId(): string {
  return crypto.randomUUID();
}

function randomKey(): string {
  const hex = Array.from(crypto.getRandomValues(new Uint8Array(16)))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
  return `sk_live_${hex}`;
}

export function mockGetCurrentUser(): User {
  return MOCK_USER;
}

export function mockGetProviders(): string[] {
  return ["github", "google"];
}

export function mockListWorkspaces(): Workspace[] {
  return [...store.workspaces];
}

export function mockGetWorkspace(id: string): Workspace | null {
  return store.workspaces.find((w) => w.id === id) ?? null;
}

export function mockListApiKeys(workspaceId: string): ApiKey[] {
  return [...(store.keys[workspaceId] ?? [])];
}

export function mockListDeployments(workspaceId: string): Deployment[] {
  return [...(store.deployments[workspaceId] ?? [])];
}

export function mockCreateWorkspace(name?: string): Workspace {
  const base = name ? slugify(name) : randomSlug();
  const slug = uniqueSlug(base);
  const workspace: Workspace = {
    id: randomId(),
    slug,
    name: name ?? slug,
    plan: "free",
    created_at: new Date().toISOString(),
  };
  store.workspaces.unshift(workspace);
  store.keys[workspace.id] = [];
  store.deployments[workspace.id] = [];
  return workspace;
}

export function mockIssueKey(workspaceId: string): ApiKeyCreated {
  const key = randomKey();
  const apiKey: ApiKeyCreated = {
    id: randomId(),
    name: null,
    key_prefix: key.slice(0, 16),
    created_at: new Date().toISOString(),
    revoked_at: null,
    key,
  };
  if (!store.keys[workspaceId]) store.keys[workspaceId] = [];
  store.keys[workspaceId].unshift(apiKey);
  return apiKey;
}

export function mockConnectAgent(): AgentConnectResult {
  const workspace = mockCreateWorkspace();
  const key = mockIssueKey(workspace.id);
  return { workspace, key };
}

export function mockRenewKey(workspaceId: string): ApiKeyCreated {
  const keys = store.keys[workspaceId] ?? [];
  const now = new Date().toISOString();
  for (const key of keys) {
    if (!key.revoked_at) key.revoked_at = now;
  }
  return mockIssueKey(workspaceId);
}

export function mockRevokeKey(workspaceId: string, keyId: string): boolean {
  const keys = store.keys[workspaceId];
  if (!keys) return false;
  const key = keys.find((k) => k.id === keyId);
  if (!key || key.revoked_at) return false;
  key.revoked_at = new Date().toISOString();
  return true;
}

export function mockUpdateWorkspaceSlug(
  workspaceId: string,
  slug: string,
): { ok: true; data: Workspace } | { ok: false; error: string } {
  const workspace = store.workspaces.find((w) => w.id === workspaceId);
  if (!workspace) return { ok: false, error: "Workspace not found" };
  if (!SLUG_PATTERN.test(slug)) {
    return { ok: false, error: "Only lowercase letters, numbers, and hyphens are allowed" };
  }
  if (slug === workspace.slug) return { ok: true, data: workspace };
  if (uniqueSlug(slug, workspaceId) !== slug) {
    return { ok: false, error: "That slug is already taken" };
  }
  workspace.slug = slug;
  return { ok: true, data: workspace };
}

export function mockDeleteDeployment(workspaceId: string, deploymentId: string): boolean {
  const deployments = store.deployments[workspaceId];
  if (!deployments) return false;
  const index = deployments.findIndex((d) => d.id === deploymentId);
  if (index === -1) return false;
  deployments.splice(index, 1);
  return true;
}
