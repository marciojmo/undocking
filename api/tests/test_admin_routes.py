import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from undocking_api.database import get_db
from undocking_api.main import app
from undocking_api.models import User
from undocking_api.session_auth import require_user


@pytest_asyncio.fixture
async def user(db) -> User:
    account = User(email="owner@example.com", name="Owner")
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


@pytest_asyncio.fixture
async def client(db) -> AsyncIterator[AsyncClient]:
    """Client whose DB dependency is bound to the in-memory test session."""

    async def override_db() -> AsyncIterator:
        yield db

    app.dependency_overrides[get_db] = override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_client(client, user) -> AsyncClient:
    """Client with the session-auth dependency resolved to ``user``."""
    app.dependency_overrides[require_user] = lambda: user
    return client


@pytest.mark.asyncio
async def test_admin_requires_authentication(client):
    response = await client.get("/admin/workspaces")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_and_list_workspaces(auth_client):
    created = await auth_client.post("/admin/workspaces", json={"name": "Acme"})
    assert created.status_code == 201
    body = created.json()
    assert body["slug"] == "acme"

    listed = await auth_client.get("/admin/workspaces")
    assert listed.status_code == 200
    assert [w["id"] for w in listed.json()] == [body["id"]]


@pytest.mark.asyncio
async def test_issue_list_and_revoke_api_key(auth_client):
    workspace = (await auth_client.post("/admin/workspaces", json={"name": "Acme"})).json()
    ws_id = workspace["id"]

    issued = await auth_client.post(
        f"/admin/workspaces/{ws_id}/keys", json={"name": "ci"}
    )
    assert issued.status_code == 201
    raw_key = issued.json()["key"]
    assert raw_key.startswith("sk_live_")

    listed = await auth_client.get(f"/admin/workspaces/{ws_id}/keys")
    assert listed.status_code == 200
    keys = listed.json()
    assert len(keys) == 1
    assert "key" not in keys[0]
    assert keys[0]["revoked_at"] is None

    revoked = await auth_client.delete(f"/admin/workspaces/{ws_id}/keys/{keys[0]['id']}")
    assert revoked.status_code == 204

    after = (await auth_client.get(f"/admin/workspaces/{ws_id}/keys")).json()
    assert after[0]["revoked_at"] is not None


@pytest.mark.asyncio
async def test_cannot_touch_unowned_workspace(auth_client):
    unknown = str(uuid.uuid4())
    response = await auth_client.get(f"/admin/workspaces/{unknown}/keys")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_connect_agent_creates_workspace_and_key(auth_client):
    response = await auth_client.post("/admin/agents")
    assert response.status_code == 201
    body = response.json()

    assert body["workspace"]["slug"] == body["workspace"]["name"]
    assert body["key"]["key"].startswith("sk_live_")
    assert body["key"]["name"] is None

    listed = await auth_client.get("/admin/workspaces")
    assert [w["id"] for w in listed.json()] == [body["workspace"]["id"]]


@pytest.mark.asyncio
async def test_renew_key_revokes_old_and_returns_new(auth_client):
    connected = (await auth_client.post("/admin/agents")).json()
    ws_id = connected["workspace"]["id"]
    old_key = connected["key"]["key"]

    renewed = await auth_client.post(f"/admin/workspaces/{ws_id}/keys/renew")
    assert renewed.status_code == 201
    new_key = renewed.json()["key"]
    assert new_key != old_key

    keys = (await auth_client.get(f"/admin/workspaces/{ws_id}/keys")).json()
    assert len(keys) == 2
    active = [k for k in keys if k["revoked_at"] is None]
    assert len(active) == 1


@pytest.mark.asyncio
async def test_update_workspace_slug(auth_client):
    created = (await auth_client.post("/admin/workspaces", json={"name": "Acme"})).json()

    updated = await auth_client.patch(
        f"/admin/workspaces/{created['id']}", json={"slug": "new-slug"}
    )
    assert updated.status_code == 200
    assert updated.json()["slug"] == "new-slug"


@pytest.mark.asyncio
async def test_update_workspace_slug_conflict(auth_client):
    await auth_client.post("/admin/workspaces", json={"name": "Taken"})
    created = (await auth_client.post("/admin/workspaces", json={"name": "Acme"})).json()

    response = await auth_client.patch(
        f"/admin/workspaces/{created['id']}", json={"slug": "taken"}
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_update_workspace_slug_rejects_invalid_format(auth_client):
    created = (await auth_client.post("/admin/workspaces", json={"name": "Acme"})).json()

    response = await auth_client.patch(
        f"/admin/workspaces/{created['id']}", json={"slug": "Not Valid!"}
    )
    assert response.status_code == 422
