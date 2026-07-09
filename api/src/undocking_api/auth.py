import hashlib
import secrets
import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .models import ApiKey, Workspace

KEY_PREFIX_LEN = 16


def _sha256(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def generate_api_key() -> str:
    """Returns a fresh raw API key in the ``sk_live_`` format the API expects."""
    return f"sk_live_{secrets.token_hex(24)}"


async def create_api_key(
    db: AsyncSession, workspace_id: str, name: str | None = None
) -> tuple[ApiKey, str]:
    """Issues a new API key for a workspace, returning the row and the raw token.

    Only the SHA-256 hash and the 16-character prefix are persisted; the raw
    token is returned once for the caller to show the user and is never
    recoverable afterwards.

    Args:
        db: Async database session.
        workspace_id: The workspace the key is scoped to.
        name: An optional human label for the key. Workspaces now have a 1:1
            relationship with their key, so this is unset by every current
            caller and kept only for backward compatibility.

    Returns:
        A tuple of the persisted ``ApiKey`` and the raw token string.
    """
    raw = generate_api_key()
    api_key = ApiKey(
        workspace_id=uuid.UUID(workspace_id),
        key_hash=_sha256(raw),
        key_prefix=raw[:KEY_PREFIX_LEN],
        name=name,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)
    return api_key, raw


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
