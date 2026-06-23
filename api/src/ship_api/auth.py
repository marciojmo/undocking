import hashlib
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .models import ApiKey, Workspace


def _sha256(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass(frozen=True)
class WorkspaceContext:
    """The workspace and API key resolved from a request's bearer token."""

    workspace_id: str
    workspace_slug: str
    api_key_id: str


async def resolve_api_key(token: str, db: AsyncSession) -> WorkspaceContext | None:
    """Resolves a bearer token to a workspace, or None if it's invalid.

    Transport-agnostic so the REST dependency and the MCP server share one
    implementation.

    Args:
        token: The raw API key (without the ``Bearer `` prefix).
        db: Async database session.

    Returns:
        The workspace context the key is scoped to, or None when the token is
        malformed, unknown, or revoked.
    """
    if not token.startswith("sk_live_") or len(token) < 20:
        return None

    prefix = token[:16]
    key_hash = _sha256(token)

    row = (
        await db.execute(
            select(ApiKey.id, ApiKey.revoked_at, Workspace.id, Workspace.slug)
            .join(Workspace, ApiKey.workspace_id == Workspace.id)
            .where(ApiKey.key_prefix == prefix, ApiKey.key_hash == key_hash)
            .limit(1)
        )
    ).first()

    if not row or row.revoked_at:
        return None

    return WorkspaceContext(str(row[2]), row[3], str(row[0]))


async def require_api_key(
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> WorkspaceContext:
    """FastAPI dependency that resolves the bearer token, raising 401 if invalid.

    Args:
        authorization: The raw ``Authorization`` request header.
        db: Async database session.

    Returns:
        The workspace context the API key is scoped to.

    Raises:
        HTTPException: 401 if the header is missing, malformed, or the key
            is unknown or revoked.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing Authorization header")

    workspace = await resolve_api_key(authorization[7:], db)
    if workspace is None:
        raise HTTPException(401, "Invalid or revoked API key")
    return workspace
