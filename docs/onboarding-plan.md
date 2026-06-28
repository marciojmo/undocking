# Onboarding flow plan

Single-workspace onboarding: user lands on their workspace after login, already set up.
The onboarding moment (key reveal + MCP snippet) replaces the create-workspace flow.

---

## Backend — 3 changes

### 1. Auto-provision on first login (`routes/auth.py`)

After `upsert_user` in the OAuth callback, check if the user already has a workspace.
If not, create one (slug derived from `user.name` or the part of email before `@`) and
issue one deploy key named `"deploy"`. Store the raw key in
`request.session["onboarding_key"]`.

```python
workspaces = await workspace_service.list_workspaces(db, user.id)
if not workspaces:
    name = user.name or user.email.split("@")[0]
    workspace = await workspace_service.create_workspace(db, user.id, name)
    _, raw_key = await create_api_key(db, str(workspace.id), "deploy")
    request.session["onboarding_key"] = raw_key
```

### 2. New onboarding endpoints (`routes/admin.py`)

- `GET /admin/me/workspace` — returns the user's first (only) workspace; 404 if none
- `GET /admin/onboarding` — returns `{ key: str | null }` from the session (null once
  acknowledged or for returning users)
- `POST /admin/onboarding/acknowledge` — clears `request.session["onboarding_key"]`,
  returns 204

### 3. New schema (`schemas.py`)

Add `OnboardingState: { key: str | None }`.

---

## Frontend — 5 changes

### `web/src/lib/api.ts`

Add `getMyWorkspace()` and `getOnboardingState()` helpers.

### `web/src/app/dashboard/actions.ts`

Add `acknowledgeOnboardingAction()` that calls `POST /admin/onboarding/acknowledge`.

### `web/src/app/dashboard/page.tsx` — rewrite

Fetches workspace + onboarding state in parallel. Renders:
1. `OnboardingPanel` (only when `key` is present in session — first login only)
2. `DeploymentsList` (always)

No `CreateWorkspaceForm`, no workspace list, no `ApiKeysPanel`.

### `web/src/app/dashboard/workspaces/[id]/page.tsx`

Redirect to `/dashboard` — this route is no longer needed.

### `web/src/components/onboarding-panel.tsx` (new component)

The getting-started card, shown once:
- Your workspace: `/{slug}`
- Your deploy key: `sk_live_...` + copy button + "shown once" warning
- MCP config snippet (same format as the existing `mcpConfig()` in `api-keys-panel.tsx`)
  + copy button
- "Done — I've saved my key" button → calls `acknowledgeOnboardingAction`, hides the panel

---

## What doesn't change

- All existing backend endpoints (workspace CRUD, key management, deployments, MCP, serve)
- `api-keys-panel.tsx` — stays in the repo but is no longer rendered
- `create-workspace-form.tsx` — stays but is no longer rendered
- `DeploymentsList` component — unchanged, just gets the workspace ID from the new page

---

## Key decisions

- **Session storage for the onboarding key**: persists across refreshes so a user can
  close and reopen the tab and still see the key. Cleared permanently when the user clicks
  "Done" or logs out.
- **One workspace forever**: no creation UI in the dashboard. Backend endpoints remain
  for future work (e.g. a "regenerate key" escape hatch).
- **Slug derivation**: `sanitize_slug(user.name or email_prefix)` — collision handling
  already exists in `workspace_service.create_workspace` (random suffix).
