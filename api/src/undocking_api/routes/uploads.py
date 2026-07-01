"""Presigned upload reservation: the large-file deploy path.

``POST /v1/uploads`` reserves a slug and returns a presigned PUT URL. The caller
uploads the raw artifact bytes straight to the bucket, keeping them out of the
model context and off the API. The deployment starts ``"pending"`` and flips to
``"deployed"`` automatically once R2 reports the upload (see
``routes/events.py``).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import WorkspaceContext, require_api_key
from ..config import settings
from ..database import get_db
from ..schemas import UploadReserveRequest, UploadReserveResponse
from ..services import deployments as deployment_service

router = APIRouter(prefix="/v1", tags=["uploads"])


@router.post("/uploads", response_model=UploadReserveResponse, status_code=201)
async def reserve_upload(
    body: UploadReserveRequest,
    workspace: Annotated[WorkspaceContext, Depends(require_api_key)],
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> UploadReserveResponse:
    """Reserves a slug and returns a presigned URL to PUT the raw artifact to.

    The deployment is created ``"pending"`` and goes live once the bytes land in
    storage; poll ``GET /v1/deployments`` to observe the status flip.
    """
    try:
        deployment, upload_url = await deployment_service.reserve_upload(
            db,
            workspace,
            content_type=body.content_type,
            slug=body.slug,
        )
    except deployment_service.SlugTakenError as error:
        raise HTTPException(409, f'Slug "{error}" is already taken in this workspace') from error

    url = f"{settings.public_base_url}/{workspace.workspace_slug}/{deployment.slug}"
    response.headers["Location"] = url
    return UploadReserveResponse(
        id=str(deployment.id),
        url=url,
        upload_url=upload_url,
        expires_in=settings.upload_url_expiry_seconds,
        content_type=body.content_type,
        status=deployment.status,
    )
