"""Dashboard sign-in routes: the OAuth dance, logout, and the current user.

These run server-side so the browser only ever holds an HttpOnly session
cookie; the OAuth tokens never reach the client.
"""

import logging

from authlib.integrations.starlette_client import OAuthError
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..models import User
from ..oauth import enabled_providers, get_provider
from ..schemas import ProviderList, UserResponse
from ..services.users import upsert_user
from ..session_auth import login_session, logout_session, require_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _callback_uri(provider: str) -> str:
    return f"{settings.public_api_url}/auth/callback/{provider}"


@router.get("/providers", response_model=ProviderList)
async def list_providers() -> ProviderList:
    """Lists the OAuth providers that are configured, so the UI can render buttons."""
    return ProviderList(providers=enabled_providers())


@router.get("/login/{provider}")
async def login(provider: str, request: Request) -> RedirectResponse:
    """Starts the OAuth flow by redirecting the browser to the provider."""
    client = get_provider(provider)
    if client is None:
        raise HTTPException(404, f"Unknown or disabled provider: {provider}")
    return await client.authorize_redirect(request, _callback_uri(provider))


@router.get("/callback/{provider}")
async def callback(
    provider: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Completes the OAuth flow, signs the user in, and returns to the dashboard."""
    client = get_provider(provider)
    if client is None:
        raise HTTPException(404, f"Unknown or disabled provider: {provider}")

    try:
        token = await client.authorize_access_token(request)
    except OAuthError as error:
        logger.warning("OAuth callback failed for %s: %s", provider, error)
        return RedirectResponse(f"{settings.frontend_url}/?auth_error=1")

    email, name = await _fetch_identity(provider, client, token)
    if not email:
        logger.warning("OAuth provider %s returned no usable email", provider)
        return RedirectResponse(f"{settings.frontend_url}/?auth_error=1")

    user = await upsert_user(db, email=email, name=name)
    login_session(request, user)
    return RedirectResponse(f"{settings.frontend_url}/dashboard")


@router.post("/logout", status_code=204)
async def logout(request: Request) -> None:
    """Clears the session cookie."""
    logout_session(request)


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(require_user)) -> UserResponse:
    """Returns the currently signed-in user."""
    return UserResponse(id=str(user.id), email=user.email, name=user.name)


async def _fetch_identity(provider: str, client, token: dict) -> tuple[str, str]:
    """Extracts a (email, name) pair from a provider after token exchange."""
    if provider == "google":
        info = token.get("userinfo") or await client.userinfo(token=token)
        if info.get("email_verified") is False:
            return "", ""
        return info.get("email", ""), info.get("name", "")

    # GitHub. The profile email is null when the user keeps it private, so fall
    # back to the emails endpoint and pick the primary verified address.
    profile = (await client.get("user", token=token)).json()
    name = profile.get("name") or profile.get("login") or ""
    email = profile.get("email")
    if not email:
        emails = (await client.get("user/emails", token=token)).json()
        email = next(
            (e["email"] for e in emails if e.get("primary") and e.get("verified")),
            None,
        )
    return email or "", name
