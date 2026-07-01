# Undocking

A deployment platform for agent generated artifacts. Upload content via REST or
MCP, get back a public URL, and the content is served at `/{workspace}/{slug}`.
Auth is via bearer API keys scoped to a workspace. Designed for AI agents.

## Repository layout

```
undocking/
├── api/     # FastAPI backend: REST + MCP, deploy/list/delete, serving
├── web/     # Next.js admin panel
└── docs/    # Engineering docs and the implementation plan
```

| Package | Stack | Status |
|---|---|---|
| [`api/`](api/) | Python 3.12, FastAPI, PostgreSQL, R2 | Active |
| [`web/`](web/) | Next.js (App Router) | Active |

## Quickstart

### Backend

```bash
cd api
uv venv --python 3.12
uv pip install -e ".[dev]"
cp .env.example .env            # then fill in your R2 and database values
psql "$DATABASE_URL" -f schema.sql
uv run uvicorn undocking_api.main:app --port 8000
```

Requires Python 3.12+, [`uv`](https://docs.astral.sh/uv/), a PostgreSQL
database, and a Cloudflare R2 bucket (S3-compatible) for storage.

### Frontend

```bash
cd web
npm install
cp .env.example .env.local
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Requires Node.js 20+.

### Docker Compose (alternative)

Run the full stack — Postgres, API, and web — in one command:

```bash
cp api/.env.example api/.env    # fill in your R2 credentials
docker compose up --build
```

- API: [http://localhost:8000](http://localhost:8000)
- Web: [http://localhost:3000](http://localhost:3000)

## Using the API

All `/v1` REST endpoints and the `/mcp` MCP endpoint authenticate with
`Authorization: Bearer sk_live_...` API keys scoped to a workspace.

The MCP server is mounted at `http://localhost:8000/mcp` (streamable-HTTP
transport) and exposes four tools: `deploy_artifact`, `create_upload_url`,
`list_deployments`, and `delete_deployment`.

See [`docs/agent-upload-guide.md`](docs/agent-upload-guide.md) for the
agent-facing deployment guide (also served live at `GET /v1/instructions`),
and [`api/README.md`](api/README.md) for the full REST/MCP API reference.

## Documentation

- [`docs/undocking-plan.md`](docs/undocking-plan.md) — full implementation plan and architecture
- [`docs/agent-upload-guide.md`](docs/agent-upload-guide.md) — agent-facing deployment guide
- [`docs/python_best_practices.md`](docs/python_best_practices.md) — Python conventions
- [`docs/nextjs_best_practices.md`](docs/nextjs_best_practices.md) — Next.js conventions

## License

Apache License 2.0 — see [LICENSE](LICENSE).
