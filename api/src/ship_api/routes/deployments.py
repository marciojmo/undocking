from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import WorkspaceContext, require_api_key
from ..config import settings
from ..database import get_db
from ..schemas import DeploymentItem, DeployRequest, DeployResponse
from ..services import deployments as deployment_service

router = APIRouter(prefix="/v1", tags=["deployments"])


@router.post("/deployments", response_model=DeployResponse, status_code=201)
async def create_deployment(
    body: DeployRequest,
    workspace: Annotated[WorkspaceContext, Depends(require_api_key)],
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> DeployResponse:
    """Creates a deployment from an HTML or Markdown artifact and returns its public URL."""
    try:
        deployment = await deployment_service.create_deployment(
            db,
            workspace,
            content=body.content,
            content_type=body.content_type,
            slug=body.slug,
        )
    except deployment_service.SlugTakenError as error:
        raise HTTPException(409, f'Slug "{error}" is already taken in this workspace') from error

    url = f"{settings.public_base_url}/{workspace.workspace_slug}/{deployment.slug}"
    response.headers["Location"] = url
    return DeployResponse(id=str(deployment.id), url=url)


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
