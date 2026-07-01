import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from undocking_api.auth import WorkspaceContext, require_api_key
from undocking_api.database import get_db
from undocking_api.main import app
from undocking_api.services import deployments as service


@pytest_asyncio.fixture
async def client(db) -> AsyncIterator[AsyncClient]:
    async def override_db() -> AsyncIterator:
        yield db

    workspace = WorkspaceContext(
        workspace_id=str(uuid.uuid4()),
        workspace_slug="acme",
        api_key_id=str(uuid.uuid4()),
    )
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[require_api_key] = lambda: workspace
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def mock_storage(monkeypatch):
    uploaded: dict[str, str | bytes] = {}

    async def fake_upload(key: str, content: str | bytes, content_type: str) -> None:
        uploaded[key] = content

    monkeypatch.setattr(service, "upload_artifact", fake_upload)
    monkeypatch.setattr(
        service, "generate_upload_url", lambda key, ct, exp: f"https://upload.test/{key}"
    )
    return uploaded


@pytest.mark.asyncio
async def test_post_inline_deploy_is_live_immediately(client, mock_storage):
    response = await client.post(
        "/v1/deployments", json={"content_type": "text/markdown", "content": "# Hi"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "deployed"
    assert "/acme/" in body["url"]
    assert "# Hi" in mock_storage.values()


@pytest.mark.asyncio
async def test_post_inline_deploy_rejects_binary_content_type(client):
    response = await client.post(
        "/v1/deployments", json={"content_type": "image/png", "content": "fake"}
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_inline_deploy_rejects_unknown_content_type(client):
    response = await client.post(
        "/v1/deployments", json={"content_type": "application/x-custom", "content": "data"}
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_inline_deploy_requires_content(client):
    response = await client.post("/v1/deployments", json={"content_type": "text/markdown"})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_uploads_reserves_pending_upload_url(client, mock_storage):
    response = await client.post("/v1/uploads", json={"content_type": "image/png"})

    assert response.status_code == 201
    body = response.json()
    assert body["upload_url"].startswith("https://upload.test/")
    assert body["method"] == "PUT"
    assert body["expires_in"] == 900
    assert body["content_type"] == "image/png"
    assert body["status"] == "pending"
    assert "/acme/" in body["url"]
    # Reserving must not upload any bytes.
    assert mock_storage == {}


@pytest.mark.asyncio
async def test_post_uploads_accepts_binary_content_type(client, mock_storage):
    for content_type in ("image/png", "image/jpeg", "application/pdf"):
        response = await client.post("/v1/uploads", json={"content_type": content_type})
        assert response.status_code == 201, content_type


@pytest.mark.asyncio
async def test_post_uploads_rejects_unknown_content_type(client):
    response = await client.post(
        "/v1/uploads", json={"content_type": "application/x-custom"}
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_uploads_duplicate_slug_conflicts(client):
    await client.post("/v1/uploads", json={"content_type": "text/markdown", "slug": "dup"})
    second = await client.post(
        "/v1/uploads", json={"content_type": "text/markdown", "slug": "dup"}
    )

    assert second.status_code == 409


@pytest.mark.asyncio
async def test_list_shows_status(client):
    await client.post(
        "/v1/deployments", json={"content_type": "text/markdown", "content": "# Hi", "slug": "live"}
    )
    await client.post("/v1/uploads", json={"content_type": "text/markdown", "slug": "waiting"})

    listed = await client.get("/v1/deployments")

    assert listed.status_code == 200
    by_slug = {item["slug"]: item["status"] for item in listed.json()}
    assert by_slug["live"] == "deployed"
    assert by_slug["waiting"] == "pending"
