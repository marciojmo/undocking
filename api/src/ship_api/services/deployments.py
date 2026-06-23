import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import WorkspaceContext
from ..markdown import render_markdown, wrap_html
from ..models import Deployment
from ..slug import generate_slug, sanitize_slug
from ..storage import upload_artifact

logger = logging.getLogger(__name__)


class SlugTakenError(Exception):
    """Raised when an explicitly requested slug already exists in the workspace."""


class DeploymentNotFoundError(Exception):
    """Raised when no active deployment matches the given ID."""


async def create_deployment(
    db: AsyncSession,
    workspace: WorkspaceContext,
    content: str,
    content_type: str,
    slug: str | None = None,
) -> Deployment:
    """Renders content, uploads it to R2, and records the deployment.

    The deployment is always bound to ``workspace`` — the target workspace is
    taken solely from the authenticated context, never from caller input, so a
    caller cannot create content in another workspace.

    Args:
        db: Async database session.
        workspace: The authenticated workspace.
        content: Raw HTML or Markdown to publish.
        content_type: Either "html" or "markdown".
        slug: Optional caller-supplied slug; a random one is generated when omitted.

    Returns:
        The persisted deployment.

    Raises:
        SlugTakenError: If an explicit slug is already used in the workspace.
    """
    requested_slug = sanitize_slug(slug) if slug else generate_slug()

    if await _slug_exists(db, workspace.workspace_id, requested_slug):
        if slug:
            raise SlugTakenError(requested_slug)
        requested_slug = generate_slug()

    html = render_markdown(content) if content_type == "markdown" else wrap_html(content)
    storage_key = f"{workspace.workspace_id}/{requested_slug}/index.html"
    await upload_artifact(storage_key, html)

    deployment = Deployment(
        workspace_id=uuid.UUID(workspace.workspace_id),
        slug=requested_slug,
        content_type=content_type,
        storage_key=storage_key,
    )
    db.add(deployment)
    await db.commit()
    await db.refresh(deployment)
    logger.info("Deployed %s to workspace %s", deployment.id, workspace.workspace_slug)
    return deployment


async def list_deployments(
    db: AsyncSession,
    workspace: WorkspaceContext,
    limit: int = 50,
) -> list[Deployment]:
    """Returns the workspace's active deployments, newest first."""
    result = await db.execute(
        select(Deployment)
        .where(
            Deployment.workspace_id == uuid.UUID(workspace.workspace_id),
            Deployment.deleted_at.is_(None),
        )
        .order_by(desc(Deployment.created_at))
        .limit(limit)
    )
    return list(result.scalars().all())


async def delete_deployment(
    db: AsyncSession,
    workspace: WorkspaceContext,
    deployment_id: str,
) -> None:
    """Soft-deletes a deployment owned by the authenticated workspace.

    IDs are accepted as strings so every transport (REST path params, MCP tool
    arguments) can pass them uniformly without a UUID type. A value that isn't a
    valid UUID can't match any row, so it's treated as not found rather than
    surfacing a database error.

    The query is scoped to ``workspace`` as well as the ID, so a deployment that
    belongs to another workspace is treated as not found rather than deleted —
    this both enforces isolation and avoids revealing that the ID exists
    elsewhere.

    Raises:
        DeploymentNotFoundError: If ``deployment_id`` isn't a valid UUID, or no
            active deployment with this ID exists in the workspace.
    """
    try:
        parsed_id = uuid.UUID(deployment_id)
    except ValueError as error:
        raise DeploymentNotFoundError(deployment_id) from error

    result = await db.execute(
        select(Deployment)
        .where(
            Deployment.id == parsed_id,
            Deployment.workspace_id == uuid.UUID(workspace.workspace_id),
            Deployment.deleted_at.is_(None),
        )
        .limit(1)
    )
    deployment = result.scalar_one_or_none()
    if deployment is None:
        raise DeploymentNotFoundError(deployment_id)

    deployment.deleted_at = datetime.now(UTC)
    await db.commit()


async def _slug_exists(db: AsyncSession, workspace_id: str, slug: str) -> bool:
    result = await db.execute(
        select(Deployment.id)
        .where(
            Deployment.workspace_id == uuid.UUID(workspace_id),
            Deployment.slug == slug,
            Deployment.deleted_at.is_(None),
        )
        .limit(1)
    )
    return result.first() is not None
