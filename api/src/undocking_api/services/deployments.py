import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import WorkspaceContext
from ..config import settings
from ..models import Deployment
from ..slug import generate_slug, sanitize_slug
from ..storage import generate_upload_url, head_etag, upload_artifact

logger = logging.getLogger(__name__)


class SlugTakenError(Exception):
    """Raised when an explicitly requested slug already exists in the workspace."""


class DeploymentNotFoundError(Exception):
    """Raised when no active deployment matches the given ID."""


async def create_inline_deployment(
    db: AsyncSession,
    workspace: WorkspaceContext,
    content_type: str,
    slug: str | None = None,
    content: str = "",
) -> Deployment:
    """Stores inline content and records an immediately-live deployment.

    The raw bytes are supplied by the caller and uploaded by the server, so the
    deployment is ``"deployed"`` the moment this returns — there is no separate
    upload step. The stored object is the **raw** HTML or Markdown; rendering
    happens at serve time. The deployment is always bound to ``workspace`` (taken
    solely from the authenticated context), so a caller cannot create content in
    another workspace.

    Args:
        db: Async database session.
        workspace: The authenticated workspace.
        content_type: Either "html" or "markdown".
        slug: Optional caller-supplied slug; a random one is generated when omitted.
        content: Raw artifact content to store.

    Returns:
        The persisted, ``"deployed"`` deployment.

    Raises:
        SlugTakenError: If an explicit slug is already used in the workspace.
    """
    requested_slug = await _resolve_slug(db, workspace.workspace_id, slug)
    storage_key = f"{workspace.workspace_id}/{requested_slug}/source"

    await upload_artifact(storage_key, content, content_type)

    deployment = Deployment(
        workspace_id=uuid.UUID(workspace.workspace_id),
        slug=requested_slug,
        content_type=content_type,
        storage_key=storage_key,
        status="deployed",
        deployed_at=datetime.now(UTC),
    )
    db.add(deployment)
    await db.commit()
    await db.refresh(deployment)
    logger.info("Deployed %s to workspace %s", deployment.id, workspace.workspace_slug)
    return deployment


async def reserve_upload(
    db: AsyncSession,
    workspace: WorkspaceContext,
    content_type: str,
    slug: str | None = None,
) -> tuple[Deployment, str]:
    """Reserves a slug and returns a presigned URL for a direct upload.

    The raw content never passes through the API: a ``"pending"`` row is
    inserted to reserve the slug (the unique constraint backstops races) and a
    presigned PUT URL is handed back. The deployment becomes ``"deployed"`` once
    the bytes land in storage — detected from an R2 event notification (see
    :func:`mark_deployed`) with :func:`reconcile_if_uploaded` as a fallback.

    Args:
        db: Async database session.
        workspace: The authenticated workspace.
        content_type: Either "html" or "markdown".
        slug: Optional caller-supplied slug; a random one is generated when omitted.

    Returns:
        A ``(deployment, upload_url)`` pair where ``deployment`` is the pending
        row and ``upload_url`` is the presigned PUT URL.

    Raises:
        SlugTakenError: If an explicit slug is already used in the workspace.
    """
    requested_slug = await _resolve_slug(db, workspace.workspace_id, slug)
    storage_key = f"{workspace.workspace_id}/{requested_slug}/source"

    deployment = Deployment(
        workspace_id=uuid.UUID(workspace.workspace_id),
        slug=requested_slug,
        content_type=content_type,
        storage_key=storage_key,
        status="pending",
    )
    db.add(deployment)
    await db.commit()
    await db.refresh(deployment)

    upload_url = generate_upload_url(storage_key, content_type, settings.upload_url_expiry_seconds)
    logger.info("Reserved upload %s for workspace %s", deployment.id, workspace.workspace_slug)
    return deployment, upload_url


async def mark_deployed(db: AsyncSession, storage_key: str) -> Deployment | None:
    """Promotes the pending deployment at ``storage_key`` to ``"deployed"``.

    Looks up the non-deleted deployment by its storage key (used by the R2 event
    webhook). The operation is idempotent: a deployment that is already deployed
    is left untouched. An unknown key is not an error — it simply returns
    ``None`` so the webhook can ignore stray events.

    Args:
        db: Async database session.
        storage_key: The object key reported by the storage event.

    Returns:
        The matching deployment, or ``None`` if no non-deleted row owns the key.
    """
    deployment = await _by_storage_key(db, storage_key)
    if deployment is None:
        return None

    if deployment.status != "deployed":
        deployment.status = "deployed"
        deployment.deployed_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(deployment)
        logger.info("Marked %s deployed via storage event", deployment.id)
    return deployment


async def reconcile_if_uploaded(db: AsyncSession, deployment: Deployment) -> Deployment:
    """Promotes a pending deployment if its object already exists in storage.

    A safety net for missed or delayed R2 event notifications, used by the serve
    path: when a row is still ``"pending"`` but the object is actually present,
    a ``HEAD`` confirms it and the row is promoted via :func:`mark_deployed`.

    Args:
        db: Async database session.
        deployment: The deployment to reconcile.

    Returns:
        The deployment, promoted to ``"deployed"`` if the object was found.
    """
    if deployment.status != "pending":
        return deployment

    if await head_etag(deployment.storage_key) is not None:
        promoted = await mark_deployed(db, deployment.storage_key)
        if promoted is not None:
            return promoted
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


async def has_active_deployments(db: AsyncSession, workspace_id: uuid.UUID) -> bool:
    """Returns whether the workspace still has any active (non-soft-deleted) deployment."""
    result = await db.execute(
        select(Deployment.id)
        .where(Deployment.workspace_id == workspace_id, Deployment.deleted_at.is_(None))
        .limit(1)
    )
    return result.first() is not None


async def delete_deployments(
    db: AsyncSession,
    workspace: WorkspaceContext,
    deployment_ids: list[str],
) -> list[str]:
    """Soft-deletes the given deployments owned by the workspace, best-effort.

    IDs that aren't valid UUIDs, don't belong to this workspace, or are already
    soft-deleted are silently skipped rather than raising — the caller only
    needs to know which IDs were actually deleted.

    Args:
        db: Async database session.
        workspace: The authenticated/owning workspace.
        deployment_ids: Candidate IDs; invalid/foreign/already-deleted entries
            are ignored rather than raising.

    Returns:
        The subset of ``deployment_ids`` that were actually soft-deleted.
    """
    parsed_ids: list[uuid.UUID] = []
    for raw_id in deployment_ids:
        try:
            parsed_ids.append(uuid.UUID(raw_id))
        except ValueError:
            continue
    if not parsed_ids:
        return []

    result = await db.execute(
        update(Deployment)
        .where(
            Deployment.id.in_(parsed_ids),
            Deployment.workspace_id == uuid.UUID(workspace.workspace_id),
            Deployment.deleted_at.is_(None),
        )
        .values(deleted_at=datetime.now(UTC))
        .returning(Deployment.id)
    )
    deleted_ids = [str(row[0]) for row in result.all()]
    await db.commit()
    logger.info(
        "Bulk-deleted %d deployment(s) in workspace %s", len(deleted_ids), workspace.workspace_slug
    )
    return deleted_ids


async def _resolve_slug(db: AsyncSession, workspace_id: str, slug: str | None) -> str:
    """Returns a free slug for the workspace.

    An explicit slug is sanitized and must be unique (otherwise
    :class:`SlugTakenError`). An omitted slug is generated, and regenerated on
    the rare random collision.

    Raises:
        SlugTakenError: If an explicit slug is already used in the workspace.
    """
    requested_slug = sanitize_slug(slug) if slug else generate_slug()
    if await _slug_exists(db, workspace_id, requested_slug):
        if slug:
            raise SlugTakenError(requested_slug)
        requested_slug = generate_slug()
    return requested_slug


async def _by_storage_key(db: AsyncSession, storage_key: str) -> Deployment | None:
    result = await db.execute(
        select(Deployment)
        .where(
            Deployment.storage_key == storage_key,
            Deployment.deleted_at.is_(None),
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


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
