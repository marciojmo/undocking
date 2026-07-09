"""Workspace management for the dashboard.

Workspaces are owned by a user; every dashboard action is scoped to a workspace
the requester owns, enforced by :func:`get_owned_workspace`.
"""

import logging
import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Workspace
from ..slug import generate_slug, sanitize_slug

logger = logging.getLogger(__name__)


class WorkspaceNotFoundError(Exception):
    """Raised when no workspace owned by the user matches the given ID."""


class WorkspaceSlugTakenError(Exception):
    """Raised when a requested slug is already used by another workspace."""


async def create_workspace(
    db: AsyncSession, owner_id: uuid.UUID, name: str | None = None
) -> Workspace:
    """Creates a workspace owned by ``owner_id`` with a globally unique slug.

    The slug is derived from the name; on collision (slugs are unique across all
    workspaces) a short random suffix is appended until one is free.

    Args:
        db: Async database session.
        owner_id: The owning user's ID.
        name: Human-readable workspace name. When omitted, a random slug is
            generated and used as both the name and the slug.

    Returns:
        The persisted workspace.
    """
    name = name or generate_slug()
    base = sanitize_slug(name) or generate_slug()
    slug = base
    while await _slug_taken(db, slug):
        slug = f"{base}-{generate_slug(4)}"[:64]

    workspace = Workspace(slug=slug, name=name, owner_id=owner_id)
    db.add(workspace)
    await db.commit()
    await db.refresh(workspace)
    logger.info("Created workspace %s (%s) for user %s", workspace.id, slug, owner_id)
    return workspace


async def update_slug(db: AsyncSession, workspace: Workspace, new_slug: str) -> Workspace:
    """Updates a workspace's slug, enforcing global uniqueness.

    The caller (route layer) is responsible for rejecting malformed slugs via
    schema validation, so this only handles the uniqueness check.

    Args:
        db: Async database session.
        workspace: The workspace to update.
        new_slug: The already-validated candidate slug.

    Returns:
        The persisted workspace.

    Raises:
        WorkspaceSlugTakenError: If another workspace already uses ``new_slug``.
    """
    if new_slug == workspace.slug:
        return workspace

    if await _slug_taken(db, new_slug):
        raise WorkspaceSlugTakenError(new_slug)

    workspace.slug = new_slug
    await db.commit()
    await db.refresh(workspace)
    logger.info("Renamed workspace %s slug to %s", workspace.id, new_slug)
    return workspace


async def list_workspaces(db: AsyncSession, owner_id: uuid.UUID) -> list[Workspace]:
    """Returns the user's workspaces, newest first."""
    result = await db.execute(
        select(Workspace)
        .where(Workspace.owner_id == owner_id)
        .order_by(desc(Workspace.created_at))
    )
    return list(result.scalars().all())


async def get_owned_workspace(
    db: AsyncSession,
    owner_id: uuid.UUID,
    workspace_id: str,
) -> Workspace:
    """Returns a workspace owned by ``owner_id``, or raises if not found.

    Scoping the lookup to the owner means a workspace belonging to someone else
    is reported as not found rather than forbidden, so IDs aren't enumerable.

    Raises:
        WorkspaceNotFoundError: If ``workspace_id`` isn't a valid UUID or no
            workspace with that ID is owned by the user.
    """
    try:
        parsed_id = uuid.UUID(workspace_id)
    except (ValueError, TypeError) as error:
        raise WorkspaceNotFoundError(workspace_id) from error

    workspace = (
        await db.execute(
            select(Workspace)
            .where(Workspace.id == parsed_id, Workspace.owner_id == owner_id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if workspace is None:
        raise WorkspaceNotFoundError(workspace_id)
    return workspace


async def _slug_taken(db: AsyncSession, slug: str) -> bool:
    result = await db.execute(select(Workspace.id).where(Workspace.slug == slug).limit(1))
    return result.first() is not None
