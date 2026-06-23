# Ship Web (admin panel)

The Next.js (App Router) admin panel for Ship. This is **phase 2 and not yet
implemented** — this directory is a placeholder for the dashboard.

## Planned scope

A browser dashboard for humans to manage a workspace:

- Authentication (interactive session/cookie login, distinct from the agent-facing
  `sk_live_` API keys)
- Workspace management
- API key issuance and revocation
- Deployment browser (list, view, delete)

It will consume the same `/v1` REST API exposed by [`../api`](../api), so it needs
no privileged access to internals.

## Status

Not started. See [`../docs/ship-plan.md`](../docs/ship-plan.md) for the overall
plan and where this fits.

## License

Apache-2.0, same as the rest of the open-source core. Paid-tier UI (billing,
quotas, etc.) will live under a future `ee/` directory with a separate
commercial license.
