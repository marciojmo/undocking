# Ship

A deployment platform for HTML/Markdown artifacts. Upload content via REST or
MCP, get back a public URL, and the content is served at `/{workspace}/{slug}`.
Auth is via bearer API keys scoped to a workspace. Designed for AI agents.

## Open core

Ship is built as an open-core project:

- The **core** (this repository's `api/` and `web/`) is open source under the
  [Apache-2.0](LICENSE) license. It is fully functional and self-hostable.
- A future **`ee/`** directory will hold commercial, paid-tier features
  (billing, quotas, team management, and the hosted control plane). That code
  will be governed by its own commercial license and is **not** part of the
  Apache-2.0 grant. The `ee/` directory does not exist yet.

If you self-host, everything you need lives in the open-source core.

## Repository layout

```
ship/
├── api/     # FastAPI backend: REST + MCP, deploy/list/delete, serving
├── web/     # Next.js admin panel (phase 2, not yet implemented)
├── docs/    # Engineering docs and the implementation plan
└── ee/      # (planned) commercial paid-tier features, separate license
```

| Package | Stack | Status |
|---|---|---|
| [`api/`](api/) | Python 3.12, FastAPI, PostgreSQL, R2 | Active |
| [`web/`](web/) | Next.js (App Router) | Planned (phase 2) |
| `ee/` | TBD | Planned |

## Quickstart

The backend is the place to start. See [`api/README.md`](api/README.md) for full
setup, but in short:

```bash
cd api
uv venv --python 3.12
uv pip install -e ".[dev]"
cp .env.example .env            # then fill in your values
psql "$DATABASE_URL" -f schema.sql
uv run uvicorn ship_api.main:app --port 8000
```

All `/v1` endpoints and the `/mcp` MCP endpoint authenticate with
`Authorization: Bearer sk_live_...` keys scoped to a workspace.

## Documentation

- [`docs/ship-plan.md`](docs/ship-plan.md) — full implementation plan and architecture
- [`docs/python_best_practices.md`](docs/python_best_practices.md) — Python conventions
- [`docs/nextjs_best_practices.md`](docs/nextjs_best_practices.md) — Next.js conventions

## License

The open-source core is licensed under the [Apache License 2.0](LICENSE).
Future code under `ee/` will carry a separate commercial license.
