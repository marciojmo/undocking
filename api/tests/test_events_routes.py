import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from ship_api.config import settings
from ship_api.database import get_db
from ship_api.main import app
from ship_api.models import Deployment, User, Workspace

_SECRET = "test-event-secret"


@pytest_asyncio.fixture
async def client(db, monkeypatch) -> AsyncIterator[AsyncClient]:
    async def override_db() -> AsyncIterator:
        yield db

    monkeypatch.setattr(settings, "r2_event_secret", _SECRET)
    app.dependency_overrides[get_db] = override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()


async def _workspace(db) -> Workspace:
    user = User(email=f"{uuid.uuid4()}@example.com", name="Owner")
    db.add(user)
    await db.flush()
    workspace = Workspace(slug=f"ws-{uuid.uuid4().hex[:8]}", name="Acme", owner_id=user.id)
    db.add(workspace)
    await db.flush()
    return workspace


async def _pending_deployment(
    db, *, slug: str = "post", workspace: Workspace | None = None
) -> Deployment:
    if workspace is None:
        workspace = await _workspace(db)
    deployment = Deployment(
        workspace_id=workspace.id,
        slug=slug,
        content_type="text/markdown",
        storage_key=f"{workspace.id}/{slug}/source",
        status="pending",
    )
    db.add(deployment)
    await db.commit()
    await db.refresh(deployment)
    return deployment


@pytest.mark.asyncio
async def test_create_event_marks_deployment_deployed(client, db):
    deployment = await _pending_deployment(db)

    response = await client.post(
        "/internal/r2-events",
        headers={"X-Ship-Event-Secret": _SECRET},
        json={"action": "PutObject", "object": {"key": deployment.storage_key}},
    )

    assert response.status_code == 200
    assert response.json()["promoted"] == 1
    await db.refresh(deployment)
    assert deployment.status == "deployed"


@pytest.mark.asyncio
async def test_batched_events_accepted(client, db):
    workspace = await _workspace(db)
    first = await _pending_deployment(db, slug="one", workspace=workspace)
    second = await _pending_deployment(db, slug="two", workspace=workspace)

    response = await client.post(
        "/internal/r2-events",
        headers={"X-Ship-Event-Secret": _SECRET},
        json=[
            {"eventType": "PutObject", "object": {"key": first.storage_key}},
            {"eventType": "CompleteMultipartUpload", "object": {"key": second.storage_key}},
        ],
    )

    assert response.status_code == 200
    assert response.json()["promoted"] == 2


@pytest.mark.asyncio
async def test_wrong_secret_is_unauthorized(client, db):
    deployment = await _pending_deployment(db)

    response = await client.post(
        "/internal/r2-events",
        headers={"X-Ship-Event-Secret": "nope"},
        json={"action": "PutObject", "object": {"key": deployment.storage_key}},
    )

    assert response.status_code == 401
    await db.refresh(deployment)
    assert deployment.status == "pending"


@pytest.mark.asyncio
async def test_missing_secret_is_unauthorized(client, db):
    deployment = await _pending_deployment(db)

    response = await client.post(
        "/internal/r2-events",
        json={"action": "PutObject", "object": {"key": deployment.storage_key}},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unknown_key_is_noop_200(client, db):
    response = await client.post(
        "/internal/r2-events",
        headers={"X-Ship-Event-Secret": _SECRET},
        json={"action": "PutObject", "object": {"key": "unknown/key/source"}},
    )

    assert response.status_code == 200
    assert response.json()["promoted"] == 0


@pytest.mark.asyncio
async def test_non_create_action_ignored(client, db):
    deployment = await _pending_deployment(db)

    response = await client.post(
        "/internal/r2-events",
        headers={"X-Ship-Event-Secret": _SECRET},
        json={"action": "DeleteObject", "object": {"key": deployment.storage_key}},
    )

    assert response.status_code == 200
    assert response.json()["promoted"] == 0
    await db.refresh(deployment)
    assert deployment.status == "pending"


@pytest.mark.asyncio
async def test_webhook_503_when_secret_unset(client, db, monkeypatch):
    monkeypatch.setattr(settings, "r2_event_secret", "")

    response = await client.post(
        "/internal/r2-events",
        headers={"X-Ship-Event-Secret": "anything"},
        json={"action": "PutObject", "object": {"key": "k"}},
    )

    assert response.status_code == 503
