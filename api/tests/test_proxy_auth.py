import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from undocking_api.config import settings
from undocking_api.database import get_db
from undocking_api.main import app
from undocking_api.models import Deployment, User, Workspace
from undocking_api.routes import serve as serve_route
from undocking_api.session_auth import require_user

_SECRET = "test-proxy-secret"
_HEADER = "X-Undocking-Proxy-Secret"


@pytest_asyncio.fixture
async def client(db) -> AsyncIterator[AsyncClient]:
    async def override_db() -> AsyncIterator:
        yield db

    app.dependency_overrides[get_db] = override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def clear_render_cache():
    serve_route._render_cache.clear()
    yield
    serve_route._render_cache.clear()


@pytest_asyncio.fixture
async def user(db) -> User:
    account = User(email="owner@example.com", name="Owner")
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


@pytest_asyncio.fixture
async def auth_client(client, user) -> AsyncClient:
    app.dependency_overrides[require_user] = lambda: user
    return client


async def _deployment(db) -> Deployment:
    account = User(email=f"{uuid.uuid4()}@example.com", name="Owner")
    db.add(account)
    await db.flush()
    workspace = Workspace(slug="acme", name="Acme", owner_id=account.id)
    db.add(workspace)
    await db.flush()
    deployment = Deployment(
        workspace_id=workspace.id,
        slug="post",
        content_type="text/markdown",
        storage_key=f"{workspace.id}/post/source",
        status="deployed",
    )
    db.add(deployment)
    await db.commit()
    return deployment


@pytest.mark.asyncio
async def test_admin_and_auth_allowed_when_secret_unset(auth_client):
    assert (await auth_client.get("/admin/workspaces")).status_code == 200
    assert (await auth_client.get("/auth/me")).status_code == 200


@pytest.mark.asyncio
async def test_admin_rejected_without_header_when_secret_set(auth_client, monkeypatch):
    monkeypatch.setattr(settings, "proxy_shared_secret", _SECRET)
    response = await auth_client.get("/admin/workspaces")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_auth_rejected_without_header_when_secret_set(auth_client, monkeypatch):
    monkeypatch.setattr(settings, "proxy_shared_secret", _SECRET)
    response = await auth_client.get("/auth/me")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_admin_rejected_with_wrong_header(auth_client, monkeypatch):
    monkeypatch.setattr(settings, "proxy_shared_secret", _SECRET)
    response = await auth_client.get("/admin/workspaces", headers={_HEADER: "nope"})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_admin_allowed_with_correct_header(auth_client, monkeypatch):
    monkeypatch.setattr(settings, "proxy_shared_secret", _SECRET)
    response = await auth_client.get("/admin/workspaces", headers={_HEADER: _SECRET})
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_auth_allowed_with_correct_header(auth_client, monkeypatch):
    monkeypatch.setattr(settings, "proxy_shared_secret", _SECRET)
    response = await auth_client.get("/auth/me", headers={_HEADER: _SECRET})
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_v1_unaffected_by_proxy_secret(client, monkeypatch):
    monkeypatch.setattr(settings, "proxy_shared_secret", _SECRET)
    response = await client.get("/v1/instructions")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_serve_route_unaffected_by_proxy_secret(client, db, monkeypatch):
    monkeypatch.setattr(settings, "proxy_shared_secret", _SECRET)
    deployment = await _deployment(db)

    async def fake_etag(key: str) -> str:
        return '"etag-1"'

    async def fake_download(key: str) -> bytes:
        return b"content"

    monkeypatch.setattr(serve_route, "head_etag", fake_etag)
    monkeypatch.setattr(serve_route, "download_artifact", fake_download)

    response = await client.get(f"/acme/{deployment.slug}")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_internal_events_unaffected_by_proxy_secret(client, monkeypatch):
    monkeypatch.setattr(settings, "proxy_shared_secret", _SECRET)
    monkeypatch.setattr(settings, "r2_event_secret", "event-secret")
    response = await client.post(
        "/internal/r2-events",
        headers={"X-Undocking-Event-Secret": "event-secret"},
        json={"action": "PutObject", "object": {"key": "unknown/key/source"}},
    )
    assert response.status_code == 200
