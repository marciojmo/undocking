"""API-key listing and revocation for the dashboard.

Issuance lives in :mod:`undocking_api.auth` next to the hashing logic; this module
covers the management operations the dashboard needs.
"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import ApiKey

logger = logging.getLogger(__name__)


class ApiKeyNotFoundError(Exception):
    """Raised when no key matches the given ID within the workspace."""


async def list_api_keys(db: AsyncSession, workspace_id: uuid.UUID) -> list[ApiKey]:
    """Returns a workspace's keys (active and revoked), newest first."""
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.workspace_id == workspace_id)
        .order_by(desc(ApiKey.created_at))
    )
    return list(result.scalars().all())


async def revoke_api_key(db: AsyncSession, workspace_id: uuid.UUID, key_id: str) -> None:
    """Revokes a key by ID within a workspace.

    Scoped to the workspace so a key from another workspace is treated as not
    found. Revoking an already-revoked key is a no-op.

    Raises:
        ApiKeyNotFoundError: If ``key_id`` isn't a valid UUID or no key with
            that ID exists in the workspace.
    """
    try:
        parsed_id = uuid.UUID(key_id)
    except (ValueError, TypeError) as error:
        raise ApiKeyNotFoundError(key_id) from error

    api_key = (
        await db.execute(
            select(ApiKey)
            .where(ApiKey.id == parsed_id, ApiKey.workspace_id == workspace_id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if api_key is None:
        raise ApiKeyNotFoundError(key_id)

    if api_key.revoked_at is None:
        api_key.revoked_at = datetime.now(UTC)
        await db.commit()
        logger.info("Revoked API key %s in workspace %s", api_key.id, workspace_id)
