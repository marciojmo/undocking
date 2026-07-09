"""Dashboard management API: workspaces, API keys, and deployment browsing.

Every route is scoped to the signed-in user (session cookie) and, where a
workspace is involved, to a workspace that user owns. This is the human-facing
counterpart to the agent-facing ``/v1`` API.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import WorkspaceContext, create_api_key
from ..config import settings
from ..database import get_db
from ..models import User, Workspace
from ..schemas import (
    AgentConnectResponse,
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyResponse,
    DeploymentItem,
    WorkspaceCreate,
    WorkspaceResponse,
    WorkspaceUpdate,
)
from ..services import api_keys as api_key_service
from ..services import deployments as deployment_service
from ..services import workspaces as workspace_service
from ..session_auth import require_user

router = APIRouter(prefix="/admin", tags=["admin"])

CurrentUser = Annotated[User, Depends(require_user)]


async def _owned_workspace(workspace_id: str, user: User, db: AsyncSession) -> Workspace:
    try:
        return await workspace_service.get_owned_workspace(db, user.id, workspace_id)
    except workspace_service.WorkspaceNotFoundError:
        raise HTTPException(404, "Workspace not found") from None


def _to_workspace_response(workspace: Workspace) -> WorkspaceResponse:
    return WorkspaceResponse(
        id=str(workspace.id),
        slug=workspace.slug,
        name=workspace.name,
        plan=workspace.plan,
        created_at=workspace.created_at,
    )


@router.get("/workspaces", response_model=list[WorkspaceResponse])
async def list_workspaces(
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> list[WorkspaceResponse]:
    """Lists the workspaces owned by the signed-in user."""
    workspaces = await workspace_service.list_workspaces(db, user.id)
    return [_to_workspace_response(workspace) for workspace in workspaces]


@router.post("/workspaces", response_model=WorkspaceResponse, status_code=201)
async def create_workspace(
    body: WorkspaceCreate,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> WorkspaceResponse:
    """Creates a workspace owned by the signed-in user."""
    workspace = await workspace_service.create_workspace(db, user.id, body.name)
    return _to_workspace_response(workspace)


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: str,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> WorkspaceResponse:
    """Returns a single workspace owned by the signed-in user."""
    workspace = await _owned_workspace(workspace_id, user, db)
    return _to_workspace_response(workspace)


@router.patch("/workspaces/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: str,
    body: WorkspaceUpdate,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> WorkspaceResponse:
    """Updates a workspace's slug."""
    workspace = await _owned_workspace(workspace_id, user, db)
    try:
        workspace = await workspace_service.update_slug(db, workspace, body.slug)
    except workspace_service.WorkspaceSlugTakenError as error:
        raise HTTPException(409, f'Slug "{error}" is already taken') from error
    return _to_workspace_response(workspace)


@router.post("/agents", response_model=AgentConnectResponse, status_code=201)
async def connect_agent(
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> AgentConnectResponse:
    """Creates a workspace with an auto-generated slug and issues its first API key."""
    workspace = await workspace_service.create_workspace(db, user.id)
    key, raw = await create_api_key(db, str(workspace.id))
    return AgentConnectResponse(
        workspace=_to_workspace_response(workspace),
        key=ApiKeyCreated(
            id=str(key.id),
            name=key.name,
            key_prefix=key.key_prefix,
            created_at=key.created_at,
            revoked_at=key.revoked_at,
            key=raw,
        ),
    )


@router.get("/workspaces/{workspace_id}/keys", response_model=list[ApiKeyResponse])
async def list_keys(
    workspace_id: str,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> list[ApiKeyResponse]:
    """Lists a workspace's API keys (raw tokens are never returned)."""
    workspace = await _owned_workspace(workspace_id, user, db)
    keys = await api_key_service.list_api_keys(db, workspace.id)
    return [
        ApiKeyResponse(
            id=str(key.id),
            name=key.name,
            key_prefix=key.key_prefix,
            created_at=key.created_at,
            revoked_at=key.revoked_at,
        )
        for key in keys
    ]


@router.post("/workspaces/{workspace_id}/keys", response_model=ApiKeyCreated, status_code=201)
async def create_key(
    workspace_id: str,
    body: ApiKeyCreate,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ApiKeyCreated:
    """Issues a new API key and returns the raw token once."""
    workspace = await _owned_workspace(workspace_id, user, db)
    key, raw = await create_api_key(db, str(workspace.id), body.name)
    return ApiKeyCreated(
        id=str(key.id),
        name=key.name,
        key_prefix=key.key_prefix,
        created_at=key.created_at,
        revoked_at=key.revoked_at,
        key=raw,
    )


@router.post("/workspaces/{workspace_id}/keys/renew", response_model=ApiKeyCreated, status_code=201)
async def renew_key(
    workspace_id: str,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ApiKeyCreated:
    """Revokes the workspace's current key(s) and issues a fresh one."""
    workspace = await _owned_workspace(workspace_id, user, db)
    key, raw = await api_key_service.renew_api_key(db, workspace.id)
    return ApiKeyCreated(
        id=str(key.id),
        name=key.name,
        key_prefix=key.key_prefix,
        created_at=key.created_at,
        revoked_at=key.revoked_at,
        key=raw,
    )


@router.delete("/workspaces/{workspace_id}/keys/{key_id}", status_code=204)
async def revoke_key(
    workspace_id: str,
    key_id: str,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Revokes an API key."""
    workspace = await _owned_workspace(workspace_id, user, db)
    try:
        await api_key_service.revoke_api_key(db, workspace.id, key_id)
    except api_key_service.ApiKeyNotFoundError:
        raise HTTPException(404, "API key not found") from None


@router.get("/workspaces/{workspace_id}/deployments", response_model=list[DeploymentItem])
async def list_deployments(
    workspace_id: str,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> list[DeploymentItem]:
    """Lists a workspace's active deployments, newest first."""
    workspace = await _owned_workspace(workspace_id, user, db)
    context = WorkspaceContext(
        workspace_id=str(workspace.id),
        workspace_slug=workspace.slug,
        api_key_id="",
    )
    deployments = await deployment_service.list_deployments(db, context)
    base = settings.public_base_url
    return [
        DeploymentItem(
            id=str(deployment.id),
            slug=deployment.slug,
            content_type=deployment.content_type,
            status=deployment.status,
            created_at=deployment.created_at,
            url=f"{base}/{workspace.slug}/{deployment.slug}",
        )
        for deployment in deployments
    ]


@router.delete(
    "/workspaces/{workspace_id}/deployments/{deployment_id}",
    status_code=204,
)
async def delete_deployment(
    workspace_id: str,
    deployment_id: str,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-deletes a deployment in the workspace."""
    workspace = await _owned_workspace(workspace_id, user, db)
    context = WorkspaceContext(
        workspace_id=str(workspace.id),
        workspace_slug=workspace.slug,
        api_key_id="",
    )
    try:
        await deployment_service.delete_deployment(db, context, deployment_id)
    except deployment_service.DeploymentNotFoundError:
        raise HTTPException(404, "Deployment not found") from None
