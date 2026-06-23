from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, JSONResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Deployment, Workspace
from ..storage import download_artifact

router = APIRouter()


@router.get("/{workspace_slug}/{slug}")
async def serve(
    workspace_slug: str,
    slug: str,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Serves a deployed artifact's HTML, or a JSON error for missing/expired ones."""
    workspace = (
        await db.execute(select(Workspace).where(Workspace.slug == workspace_slug).limit(1))
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

    html = await download_artifact(deployment.storage_key)
    if not html:
        return JSONResponse({"error": "Not found"}, 404)

    return HTMLResponse(html)
