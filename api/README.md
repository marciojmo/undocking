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
| `POST` | `/v1/deployments` | Deploy an HTML/Markdown artifact, returns a public URL |
| `GET` | `/v1/deployments` | List active deployments (newest first) |
| `DELETE` | `/v1/deployments/{id}` | Soft-delete a deployment |
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

```bash
curl -X POST http://localhost:8000/v1/deployments \
  -H "Authorization: Bearer sk_live_..." \
  -H "Content-Type: application/json" \
  -d '{"content": "# Hello", "content_type": "markdown"}'
```

## MCP

The MCP server is mounted at `/mcp` using the streamable-HTTP transport and
exposes three tools: `deploy_artifact`, `list_deployments`, and
`delete_deployment`. It authenticates with the same `sk_live_` bearer tokens
as the REST API.

## Development

```bash
uv run pytest        # run tests
uv run ruff check .  # lint
```
