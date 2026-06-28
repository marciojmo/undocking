from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import WorkspaceContext, require_api_key
from ..config import settings
from ..database import get_db
from ..instructions import agent_upload_guide
from ..schemas import DeploymentItem, DeployRequest, DeployResponse
from ..services import deployments as deployment_service

router = APIRouter(prefix="/v1", tags=["deployments"])


@router.get("/instructions", response_class=PlainTextResponse)
async def instructions() -> PlainTextResponse:
    """Returns the agent upload guide as Markdown. No authentication required."""
    return PlainTextResponse(agent_upload_guide(), media_type="text/markdown; charset=utf-8")


@router.post("/deployments", response_model=DeployResponse, status_code=201)
async def create_deployment(
    body: DeployRequest,
    workspace: Annotated[WorkspaceContext, Depends(require_api_key)],
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> DeployResponse:
    """Creates a deployment from inline content and returns its public URL.

    The artifact bytes are sent in the request body and the deployment is live
    immediately (``status`` is ``"deployed"``). For large files, reserve a
    presigned upload via ``POST /v1/uploads`` instead.
    """
    try:
        deployment = await deployment_service.create_inline_deployment(
            db,
            workspace,
            content_type=body.content_type,
            slug=body.slug,
            content=body.content,
        )
    except deployment_service.SlugTakenError as error:
        raise HTTPException(409, f'Slug "{error}" is already taken in this workspace') from error

    url = f"{settings.public_base_url}/{workspace.workspace_slug}/{deployment.slug}"
    response.headers["Location"] = url
    return DeployResponse(id=str(deployment.id), url=url, status=deployment.status)


@router.get("/deployments", response_model=list[DeploymentItem])
async def list_deployments(
    workspace: Annotated[WorkspaceContext, Depends(require_api_key)],
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[DeploymentItem]:
    """Lists the workspace's active deployments, newest first."""
    deployments = await deployment_service.list_deployments(db, workspace, limit=limit)
    base = settings.public_base_url
    return [
        DeploymentItem(
            id=str(deployment.id),
            slug=deployment.slug,
            content_type=deployment.content_type,
            status=deployment.status,
            created_at=deployment.created_at,
            url=f"{base}/{workspace.workspace_slug}/{deployment.slug}",
        )
        for deployment in deployments
    ]


@router.delete("/deployments/{deployment_id}", status_code=204)
async def delete_deployment(
    deployment_id: str,
    workspace: Annotated[WorkspaceContext, Depends(require_api_key)],
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-deletes a deployment by ID. Returns 204 No Content on success."""
    try:
        await deployment_service.delete_deployment(db, workspace, deployment_id)
    except deployment_service.DeploymentNotFoundError as error:
        raise HTTPException(404, "Deployment not found") from error
