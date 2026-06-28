# Ship API

A deployment platform for HTML/Markdown artifacts. Upload content via REST or
MCP, get back a public URL, and the content is served at `/{workspace}/{slug}`.
Auth is via bearer API keys scoped to a workspace. Designed for AI agents.

## Requirements

- Python 3.12+
- PostgreSQL
- A Cloudflare R2 bucket (S3-compatible)

## Setup

```bash
cd api
uv venv --python 3.12
uv pip install -e ".[dev]"
cp .env.example .env   # then fill in your values
```

Apply the database schema:

```bash
psql "$DATABASE_URL" -f schema.sql
```

You can create workspaces and API keys two ways: through the admin panel
([`../web`](../web), see the dashboard endpoints below), or by seeding the
database directly. To seed manually, see [`schema.sql`](schema.sql) for the table
definitions; insert a `users` row, a `workspaces` row, and an `api_keys` row
whose `key_hash` is the SHA-256 hex digest of your raw key and whose `key_prefix`
is the first 16 characters of it. Keys must start with `sk_live_`.

## Running

```bash
uv run uvicorn ship_api.main:app --port 8000
```

## API

All `/v1` endpoints require an `Authorization: Bearer sk_live_...` header.

| Method | Path | Description |
|---|---|---|
| `POST` | `/v1/deployments` | Inline deploy; stores the content and goes live immediately |
| `POST` | `/v1/uploads` | Reserve a presigned upload URL for large files (row starts `pending`) |
| `GET` | `/v1/deployments` | List active deployments with status (newest first) |
| `DELETE` | `/v1/deployments/{id}` | Soft-delete a deployment |
| `GET` | `/v1/instructions` | Agent upload guide as Markdown (no auth) |
| `POST` | `/internal/r2-events` | R2 event webhook; flips `pending` rows to `deployed` (shared-secret auth, no API key) |
| `GET` | `/{workspace}/{slug}` | Public serving of a deployed artifact |
| `*` | `/mcp` | MCP streamable-HTTP endpoint (same auth) |

### Dashboard auth & admin (phase 2)

The admin panel ([`../web`](../web)) signs users in via OAuth and manages
workspaces and keys. These routes authenticate with a session **cookie** (set
after sign-in), not the `sk_live_` bearer tokens.

| Method | Path | Description |
|---|---|---|
| `GET` | `/auth/providers` | Lists configured OAuth providers |
| `GET` | `/auth/login/{provider}` | Starts the OAuth flow (`github` / `google`) |
| `GET` | `/auth/callback/{provider}` | OAuth callback; sets the session cookie |
| `POST` | `/auth/logout` | Clears the session |
| `GET` | `/auth/me` | Current signed-in user |
| `GET/POST` | `/admin/workspaces` | List / create the user's workspaces |
| `GET` | `/admin/workspaces/{id}` | Get a single owned workspace |
| `GET/POST` | `/admin/workspaces/{id}/keys` | List / issue API keys (raw key shown once) |
| `DELETE` | `/admin/workspaces/{id}/keys/{key_id}` | Revoke an API key |
| `GET` | `/admin/workspaces/{id}/deployments` | List the workspace's deployments |
| `DELETE` | `/admin/workspaces/{id}/deployments/{dep_id}` | Soft-delete a deployment |

To enable sign-in, set `SESSION_SECRET` and at least one provider's OAuth
credentials in `.env` (see [`.env.example`](.env.example)). The OAuth callback to
register with the provider is `{PUBLIC_API_URL}/auth/callback/{provider}` (in dev,
`http://localhost:3000/api/auth/callback/github`).

### Deploy example

For small files, deploy inline in one step; the URL is live immediately
(`status` is `"deployed"`):

```bash
curl -X POST http://localhost:8000/v1/deployments \
  -H "Authorization: Bearer sk_live_..." \
  -H "Content-Type: application/json" \
  -d '{"content": "# Hello", "content_type": "markdown"}'
# -> { "id": "...", "url": "...", "status": "deployed" }
```

For large files, reserve a presigned upload (the artifact never passes through
the API), then PUT the bytes straight to the bucket:

```bash
curl -X POST http://localhost:8000/v1/uploads \
  -H "Authorization: Bearer sk_live_..." \
  -H "Content-Type: application/json" \
  -d '{"content_type": "markdown"}'
# -> { "url": "...", "upload_url": "...", "expires_in": 900, "method": "PUT", "status": "pending" }

curl -X PUT --upload-file ./artifact.md "<upload_url>"
```

The reserved deployment starts `pending` and serves `404` until the upload
lands. There is no confirm call: an R2 event notification flips it to `deployed`
(a lazy `HEAD` reconcile on the serve path is the fallback for missed events).

Content is stored raw and rendered (Markdown -> styled HTML, HTML -> wrapped) on
each request to `/{workspace}/{slug}`. The full agent guide is served at
`GET /v1/instructions` (see also [`../docs/agent-upload-guide.md`](../docs/agent-upload-guide.md)).

#### R2 event wiring (Cloudflare-side, outside this repo)

Automatic `pending` -> `deployed` promotion relies on Cloudflare wiring that
lives outside this repo: enable **R2 Event Notifications** on the bucket ->
**Cloudflare Queue** -> a small **consumer/Worker** that POSTs each event to
`/internal/r2-events` with the `X-Ship-Event-Secret` header set to
`R2_EVENT_SECRET`. The endpoint accepts a single event or a batch, ignores
unrelated keys, and is idempotent.

## MCP

The MCP server is mounted at `/mcp` using the streamable-HTTP transport and
exposes four tools: `deploy_artifact`, `create_upload_url`, `list_deployments`,
and `delete_deployment`. It authenticates with the same `sk_live_` bearer tokens
as the REST API. The deploy guide is also exposed as the `how_to_deploy` prompt
and the `ship://guide/deploy` resource.

`deploy_artifact` takes inline `content` and is live immediately (`status:
"deployed"`). `create_upload_url` reserves a presigned `upload_url` for large
files; the deployment starts `pending` and flips to `deployed` once the upload
lands (poll `list_deployments` to observe it).

## Development

```bash
uv run pytest        # run tests
uv run ruff check .  # lint
```
