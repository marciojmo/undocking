# CLAUDE.md

Guidance for working in this repository.

## Project

**Undocking** — a platform for publishing LLM-generated artifacts to the web. Agents upload any artifact (HTML, Markdown, images, PDFs, JSON, etc.) via REST or MCP, get back a public URL, and the artifact is served at `/{workspace}/{slug}` with its native MIME type. Auth is via bearer API keys scoped to a workspace.

- Backend: Python + FastAPI (`api/`)
- Admin panel: Next.js (`web/`, phase 2)
- See [`docs/undocking-plan.md`](docs/undocking-plan.md) for the full implementation plan and architecture.

## Required reading

Follow these docs when writing code:

- [`docs/python_best_practices.md`](docs/python_best_practices.md) — conventions for all Python code (`**/*.py`).
- [`docs/nextjs_best_practices.md`](docs/nextjs_best_practices.md) — App Router patterns for the Next.js admin panel (`**/*.ts`, `**/*.tsx`).
