# Ship Web (admin panel)

The Next.js (App Router) admin panel for Ship. A browser dashboard for humans to
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
- The [`../api`](../api) backend running (defaults to `http://localhost:8000`)

## Setup

```bash
cd web
npm install
cp .env.example .env.local   # adjust if the API runs elsewhere
```

`.env.local` settings:

- `API_PROXY_TARGET` — where the browser-facing `/api/*` proxy forwards to.
- `API_INTERNAL_URL` — base URL the Next.js server uses for SSR data fetching.

## Running

```bash
npm run dev      # http://localhost:3000
```

Sign-in requires OAuth credentials configured on the API side (see
[`../api/.env.example`](../api/.env.example)). With none set, the landing page
shows that no providers are configured.

## Development

```bash
npm run lint
npm run build
```

## License

Apache-2.0, same as the rest of the open-source core. Paid-tier UI (billing,
quotas, etc.) will live under a future `ee/` directory with a separate
commercial license.
