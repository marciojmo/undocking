from cachetools import LRUCache
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, JSONResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..markdown import render_markdown
from ..models import Deployment, Workspace
from ..services import deployments as deployment_service
from ..storage import download_artifact, head_etag

router = APIRouter()

# Render cache for Markdown only: keyed by storage key, validated by ETag.
# Artifacts are effectively immutable, so this avoids re-rendering unchanged bytes.
_render_cache: LRUCache[str, tuple[str, str]] = LRUCache(maxsize=1024)


@router.get("/{workspace_slug}/{slug}")
async def serve(
    workspace_slug: str,
    slug: str,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Serves a deployed artifact with its native MIME type, or a JSON error if missing."""
    workspace = (
        await db.execute(
            select(Workspace)
            .where(Workspace.slug == workspace_slug, Workspace.deleted_at.is_(None))
            .limit(1)
        )
    ).scalar_one_or_none()
    if not workspace:
        return JSONResponse({"error": "Not found"}, 404)

    deployment = (
        await db.execute(
            select(Deployment)
            .where(
                Deployment.workspace_id == workspace.id,
                Deployment.slug == slug,
                Deployment.deleted_at.is_(None),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if not deployment:
        return JSONResponse({"error": "Not found"}, 404)

    # A pending row isn't live yet. Try a lazy reconcile in case the R2 event
    # was missed or delayed; if it's still pending, the upload hasn't landed.
    if deployment.status == "pending":
        deployment = await deployment_service.reconcile_if_uploaded(db, deployment)
        if deployment.status == "pending":
            return JSONResponse({"error": "Not found"}, 404)

    etag = await head_etag(deployment.storage_key)
    if etag is None:
        # The row exists but no bytes have been uploaded yet (or the object is gone).
        return JSONResponse({"error": "Not found"}, 404)

    content_type = deployment.content_type

    # Only Markdown benefits from render caching (rendering is CPU-bound).
    if content_type == "text/markdown":
        cached = _render_cache.get(deployment.storage_key)
        if cached and cached[0] == etag:
            return HTMLResponse(cached[1])

    raw = await download_artifact(deployment.storage_key)
    if raw is None:
        return JSONResponse({"error": "Not found"}, 404)

    if content_type == "text/markdown":
        rendered = render_markdown(raw.decode())
        _render_cache[deployment.storage_key] = (etag, rendered)
        return HTMLResponse(rendered)

    return Response(content=raw, media_type=content_type)
