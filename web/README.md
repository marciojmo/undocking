# Undocking Web (admin panel)

The Next.js (App Router) admin panel for Undocking. A browser dashboard for humans to
manage a workspace, separate from the agent-facing `sk_live_` API keys.

## Scope (phase 2)

- OAuth sign-in (GitHub / Google), distinct from the `sk_live_` agent keys
- Workspace management (create, list)
- API key issuance (shown once) and revocation
- Deployment browser (list, view, delete)

It consumes the `/v1` and `/admin` REST APIs exposed by [`../api`](../api). The
API owns the database and runs the OAuth flow; this app is a thin client.

## Architecture

The browser only ever talks to the Next.js origin. `next.config.ts` rewrites
`/api/*` to the FastAPI backend so the session cookie stays first-party (no
CORS). Server Components and Server Actions call the backend directly and forward
the session cookie via [`src/lib/api.ts`](src/lib/api.ts).

```
src/app/
  page.tsx                         # Public landing page + sign-in
  dashboard/
    layout.tsx                     # Auth gate (/auth/me) + header
    page.tsx                       # Workspaces list + create
    actions.ts                     # Server Actions (create/issue/revoke/delete)
    workspaces/[id]/page.tsx       # API keys + deployments for a workspace
```

## Requirements

- Node.js 20+
- The [`../api`](../api) backend when using real auth and data (defaults to
  `http://localhost:8000`). Not required for web-only UI development — see below.

## Setup

```bash
cd web
npm install
cp .env.example .env.local   # adjust if the API runs elsewhere
```

`.env.local` settings:

- `API_PROXY_TARGET` — where the browser-facing `/api/*` proxy forwards to.
- `API_INTERNAL_URL` — base URL the Next.js server uses for SSR data fetching.
- `NEXT_PUBLIC_API_URL` — public origin of the FastAPI backend, baked into the
  agent connection prompt (MCP endpoint = `<origin>/mcp`, REST = `<origin>/v1`).
  Agents connect to the API directly, never through this app's `/api` proxy. In
  production set it to the API's public URL (the API's `PUBLIC_BASE_URL`);
  defaults to `http://localhost:8000`. `NEXT_PUBLIC_MCP_URL` optionally
  overrides the MCP endpoint alone.
- `DEV_MOCK_API` — set to `true` for in-memory fixtures (no API or Postgres).

## Running

```bash
npm run dev      # http://localhost:3000
```

Sign-in requires OAuth credentials configured on the API side (see
[`../api/.env.example`](../api/.env.example)). With none set, the landing page
shows that no providers are configured.

## Web-only development

Work on the landing page or dashboard UI without running the API or database:

```bash
cd web
cp .env.example .env.local   # DEV_MOCK_API=true
npm run dev                  # http://localhost:3000
```

With `DEV_MOCK_API=true`, the app serves in-memory fixtures (signed-in user,
workspaces, API keys, deployments). A banner in the dashboard indicates mock
mode. OAuth sign-in is bypassed — the fixture user is returned from
`getCurrentUser`.

Omit `DEV_MOCK_API` or set it to `false` when running against a real local API
(`npm run dev` in web plus the API on port 8000).

The landing page also degrades gracefully when the API is unreachable (no mock
flag needed): sign-in shows no providers and the marketing sections still render.

## Development

```bash
npm run lint
npm run build
```

## License

Apache-2.0.
