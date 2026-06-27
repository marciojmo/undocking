# Ship Deployment Guide

This is the agent-facing guide for publishing artifacts to Ship. The API serves
the same text at `GET /v1/instructions`, and the MCP server exposes it as the
`how_to_deploy` prompt and the `ship://guide/deploy` resource. Replace
`https://ship.example.com` below with your deployment's base URL.

Auth: `Authorization: Bearer sk_live_...` (required on all requests)

## Choose a path

| Size   | Method                       | Endpoint                            |
|--------|------------------------------|-------------------------------------|
| ≤ 1 MB | Inline deploy (one step)     | POST /v1/deployments                |
| > 1 MB | Presigned upload (two steps) | POST /v1/uploads → PUT <upload_url> |

## Inline deploy

```bash
curl -sX POST https://ship.example.com/v1/deployments \
  -H "Authorization: Bearer sk_live_..." \
  -H "Content-Type: application/json" \
  -d '{"content": "# Hello", "content_type": "markdown"}'
```

Response — URL is live immediately:

```json
{"id": "...", "url": "https://ship.example.com/<workspace>/<slug>", "status": "deployed"}
```

## Presigned upload

Step 1 — reserve:

```bash
curl -sX POST https://ship.example.com/v1/uploads \
  -H "Authorization: Bearer sk_live_..." \
  -H "Content-Type: application/json" \
  -d '{"content_type": "markdown"}'
```

```json
{"id": "...", "url": "https://ship.example.com/<workspace>/<slug>", "upload_url": "https://...",
 "expires_in": 900, "method": "PUT", "status": "pending"}
```

Step 2 — PUT raw bytes (no auth header):

```bash
curl -X PUT --upload-file ./artifact.md "<upload_url>"
```

Status flips `"pending"` → `"deployed"` automatically once the upload lands.
`upload_url` is single-use and expires after `expires_in` seconds.

## Fields

- `content_type` (required): `"markdown"` | `"html"`. Markdown is rendered to a
  styled page; HTML is wrapped as a body fragment — send inner markup only, not a
  full `<html>` document.
- `content` (required for inline): raw artifact, ≤ 1 MB.
- `slug` (optional): URL path segment. Auto-generated if omitted. Returns 409 if taken.

## List & delete

```bash
GET    https://ship.example.com/v1/deployments       # newest first; includes status
DELETE https://ship.example.com/v1/deployments/<id>  # soft-delete; returns 204
```
