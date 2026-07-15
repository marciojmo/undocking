# Undocking Deployment Guide

This is the agent-facing guide for publishing artifacts to Undocking. The API serves
the same text at `GET /v1/instructions`, and the MCP server exposes it as the
`how_to_deploy` prompt and the `undocking://guide/deploy` resource. Replace
`https://undocking.io` below with your deployment's base URL.

Undocking publishes LLM-generated artifacts to public URLs. Use it whenever the
user asks to publish, undock, deploy, share, or host an artifact ("publish this
report", "undock this page", "share this as a link").

Auth: `Authorization: Bearer sk_live_...` (required on all requests).

## Endpoints

Both interfaces are served directly by the Undocking API at `https://undocking.io` — call it
directly, never through the dashboard/web origin.

- MCP (streamable HTTP): `https://undocking.io/mcp` — tools `deploy_artifact`,
  `create_upload_url`, `list_deployments`, `delete_deployment`. Send the same
  `Authorization: Bearer sk_live_...` header.
- REST: `https://undocking.io/v1` — documented below.

## Choose a path

| Content          | Method                       | Endpoint                            |
|------------------|------------------------------|-------------------------------------|
| Text, ≤ 1 MB     | Inline deploy (one step)     | POST /v1/deployments                |
| Binary or > 1 MB | Presigned upload (two steps) | POST /v1/uploads → PUT <upload_url> |

## Supported content types

**Inline deploy** (`POST /v1/deployments`) — text-based only:

| content_type       | Served as                          |
|--------------------|------------------------------------|
| `text/html`        | HTML document (served as-is)       |
| `text/markdown`    | Rendered to a styled HTML page     |
| `text/plain`       | Plain text                         |
| `text/csv`         | CSV                                |
| `application/json` | JSON                               |
| `image/svg+xml`    | SVG image                          |

**Presigned upload** (`POST /v1/uploads`) — all of the above plus:

| content_type       | Served as    |
|--------------------|--------------|
| `image/png`        | PNG image    |
| `image/jpeg`       | JPEG image   |
| `image/gif`        | GIF image    |
| `image/webp`       | WebP image   |
| `application/pdf`  | PDF document |

## Inline deploy

    curl -sX POST https://undocking.io/v1/deployments \
      -H "Authorization: Bearer sk_live_..." \
      -H "Content-Type: application/json" \
      -d '{"content": "# Hello", "content_type": "text/markdown"}'

Response — URL is live immediately:

    {"id": "...", "url": "https://undocking.io/<workspace>/<slug>", "status": "deployed"}

## Presigned upload

Step 1 — reserve:

    curl -sX POST https://undocking.io/v1/uploads \
      -H "Authorization: Bearer sk_live_..." \
      -H "Content-Type: application/json" \
      -d '{"content_type": "image/png"}'

    {"id": "...", "url": "https://undocking.io/<workspace>/<slug>", "upload_url": "https://...",
     "expires_in": 900, "method": "PUT", "content_type": "image/png", "status": "pending"}

Step 2 — PUT raw bytes with matching Content-Type header:

    curl -X PUT -H "Content-Type: image/png" --upload-file ./image.png "<upload_url>"

Status flips `"pending"` → `"deployed"` automatically once the upload lands.
`upload_url` is single-use and expires after `expires_in` seconds.

## Fields

- `content_type` (required): MIME type from the tables above.
- `content` (required for inline): raw artifact as a string, ≤ 1 MB.
- `slug` (optional): URL path segment. Auto-generated if omitted. Returns 409 if taken.

## List & delete

    GET    https://undocking.io/v1/deployments       # newest first; includes status
    DELETE https://undocking.io/v1/deployments/<id>  # soft-delete; returns 204
