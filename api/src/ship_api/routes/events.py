"""Internal R2 event-notification webhook.

R2 delivers object-notification events through a Cloudflare Queue; a small
consumer/Worker (configured in Cloudflare, not this repo) forwards them here.
Each object-create event promotes the matching pending deployment to
``"deployed"`` via its storage key.

This endpoint is *not* part of the ``/v1`` API-key surface — it is
machine-to-machine and guarded by a shared secret compared in constant time.
"""

import hmac
import logging

from fastapi import APIRouter, Body, Depends, Header, HTTPException
from pydantic import TypeAdapter
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..schemas import R2Event
from ..services import deployments as deployment_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["events"])

# R2 actions that mean an object now exists at the key.
_CREATE_ACTIONS = frozenset({"PutObject", "CompleteMultipartUpload", "CopyObject"})

# Accepts either a single event object or a batch (array) of them.
_events_adapter: TypeAdapter[R2Event | list[R2Event]] = TypeAdapter(R2Event | list[R2Event])


@router.post("/r2-events")
async def r2_events(
    payload: dict | list = Body(...),
    x_ship_event_secret: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Promotes pending deployments for the object-create events in ``payload``.

    Accepts a single event or a batch. Unknown object keys and non-create
    actions are ignored. Always returns 200 for an authenticated, well-formed
    payload so the queue consumer does not retry indefinitely.

    Raises:
        HTTPException: 503 if the shared secret is unset, 401 on mismatch.
    """
    if not settings.r2_event_secret:
        raise HTTPException(503, "Event webhook is not configured")
    if not hmac.compare_digest(x_ship_event_secret, settings.r2_event_secret):
        raise HTTPException(401, "Invalid event secret")

    parsed = _events_adapter.validate_python(payload)
    events = parsed if isinstance(parsed, list) else [parsed]

    promoted = 0
    for event in events:
        action = event.action_name()
        key = event.object_key()
        if key is None or (action is not None and action not in _CREATE_ACTIONS):
            continue
        deployment = await deployment_service.mark_deployed(db, key)
        if deployment is not None and deployment.status == "deployed":
            promoted += 1

    return {"promoted": promoted, "received": len(events)}
