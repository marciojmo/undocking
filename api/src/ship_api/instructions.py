"""The canonical agent-facing guide for uploading artifacts to Ship.

A single source of truth surfaced three ways: the ``GET /v1/instructions`` REST
endpoint, an MCP prompt and resource, and a committed copy at
``docs/agent-upload-guide.md``.
"""

from .config import settings


def agent_upload_guide() -> str:
    """Returns the agent upload guide as Markdown, with URLs filled in from config."""
    base = settings.public_base_url
    return f"""# Ship Deployment Guide

Auth: `Authorization: Bearer sk_live_...` (required on all requests)

## Choose a path

| Size   | Method                       | Endpoint                            |
|--------|------------------------------|-------------------------------------|
| ≤ 1 MB | Inline deploy (one step)     | POST /v1/deployments                |
| > 1 MB | Presigned upload (two steps) | POST /v1/uploads → PUT <upload_url> |

## Inline deploy

    curl -sX POST {base}/v1/deployments \\
      -H "Authorization: Bearer sk_live_..." \\
      -H "Content-Type: application/json" \\
      -d '{{"content": "# Hello", "content_type": "markdown"}}'

Response — URL is live immediately:

    {{"id": "...", "url": "{base}/<workspace>/<slug>", "status": "deployed"}}

## Presigned upload

Step 1 — reserve:

    curl -sX POST {base}/v1/uploads \\
      -H "Authorization: Bearer sk_live_..." \\
      -H "Content-Type: application/json" \\
      -d '{{"content_type": "markdown"}}'

    {{"id": "...", "url": "{base}/<workspace>/<slug>", "upload_url": "https://...",
     "expires_in": 900, "method": "PUT", "status": "pending"}}

Step 2 — PUT raw bytes (no auth header):

    curl -X PUT --upload-file ./artifact.md "<upload_url>"

Status flips `"pending"` → `"deployed"` automatically once the upload lands.
`upload_url` is single-use and expires after `expires_in` seconds.

## Fields

- `content_type` (required): `"markdown"` | `"html"`. Markdown is rendered to a
  styled page; HTML is wrapped as a body fragment — send inner markup only, not a
  full `<html>` document.
- `content` (required for inline): raw artifact, ≤ 1 MB.
- `slug` (optional): URL path segment. Auto-generated if omitted. Returns 409 if taken.

## List & delete

    GET    {base}/v1/deployments       # newest first; includes status
    DELETE {base}/v1/deployments/<id>  # soft-delete; returns 204
"""
