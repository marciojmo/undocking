"""Restricts /admin and /auth to requests forwarded by the undocking.io proxy.

These are the dashboard's session-cookie routes — meant to be reached only via
the Next.js app's same-origin /api/* proxy, never hit directly against the
API's own host. The proxy attaches a shared secret to every request it
forwards; this dependency rejects anything else.
"""

import hmac
from typing import Annotated

from fastapi import Header, HTTPException

from .config import settings


async def require_proxy_secret(
    x_undocking_proxy_secret: Annotated[str | None, Header()] = None,
) -> None:
    """FastAPI dependency raising 404 if the request didn't come through the proxy.

    Skipped entirely when PROXY_SHARED_SECRET is unset (local dev default).

    Raises:
        HTTPException: 404 if the header is missing or doesn't match. 404 rather
            than 401 so a direct probe doesn't confirm anything lives here.
    """
    if not settings.proxy_shared_secret:
        return
    if not hmac.compare_digest(x_undocking_proxy_secret or "", settings.proxy_shared_secret):
        raise HTTPException(404, "Not found")
