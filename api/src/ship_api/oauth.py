"""OAuth client registry for dashboard sign-in.

The API runs the OAuth dance on behalf of the dashboard so the database and key
issuance stay behind a single backend. Each provider is registered only when its
credentials are configured, so deployments can enable GitHub, Google, or both.
"""

import logging

from authlib.integrations.starlette_client import OAuth, StarletteOAuth2App

from .config import settings

logger = logging.getLogger(__name__)

oauth = OAuth()

if settings.github_client_id and settings.github_client_secret:
    oauth.register(
        name="github",
        client_id=settings.github_client_id,
        client_secret=settings.github_client_secret,
        access_token_url="https://github.com/login/oauth/access_token",
        authorize_url="https://github.com/login/oauth/authorize",
        api_base_url="https://api.github.com/",
        client_kwargs={"scope": "read:user user:email"},
    )

if settings.google_client_id and settings.google_client_secret:
    oauth.register(
        name="google",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


def get_provider(name: str) -> StarletteOAuth2App | None:
    """Returns the registered OAuth client for ``name``, or None if it's disabled."""
    return oauth.create_client(name)


def enabled_providers() -> list[str]:
    """Returns the names of providers that have credentials configured."""
    return [name for name in ("github", "google") if oauth.create_client(name) is not None]
