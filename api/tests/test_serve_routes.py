import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from ship_api.database import get_db
from ship_api.main import app
from ship_api.models import Deployment, User, Workspace
from ship_api.routes import serve as serve_route
from ship_api.services import deployments as deployment_service


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


async def _make_deployment(
    db, *, content_type: str, slug: str = "post", status: str = "deployed"
) -> Deployment:
    user = User(email=f"{uuid.uuid4()}@example.com", name="Owner")
    db.add(user)
    await db.flush()
    workspace = Workspace(slug="acme", name="Acme", owner_id=user.id)
    db.add(workspace)
    await db.flush()
    deployment = Deployment(
        workspace_id=workspace.id,
        slug=slug,
        content_type=content_type,
        storage_key=f"{workspace.id}/{slug}/source",
        status=status,
    )
    db.add(deployment)
    await db.commit()
    return deployment


@pytest.mark.asyncio
async def test_serve_renders_markdown(client, db, monkeypatch):
    await _make_deployment(db, content_type="text/markdown")

    async def fake_etag(key: str) -> str:
        return '"etag-1"'

    async def fake_download(key: str) -> bytes:
        return b"# Title"

    monkeypatch.setattr(serve_route, "head_etag", fake_etag)
    monkeypatch.setattr(serve_route, "download_artifact", fake_download)

    response = await client.get("/acme/post")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "<h1>Title</h1>" in response.text


@pytest.mark.asyncio
async def test_serve_html_as_is(client, db, monkeypatch):
    await _make_deployment(db, content_type="text/html")

    monkeypatch.setattr(serve_route, "head_etag", lambda key: _async('"e"'))
    monkeypatch.setattr(serve_route, "download_artifact", lambda key: _async(b"<p>hi</p>"))

    response = await client.get("/acme/post")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "<p>hi</p>" in response.text
    # HTML is served as-is, not wrapped in a shell.
    assert "<!DOCTYPE html>" not in response.text


@pytest.mark.asyncio
async def test_serve_image_with_correct_mime(client, db, monkeypatch):
    await _make_deployment(db, content_type="image/png")

    fake_bytes = b"\x89PNG\r\n\x1a\n"
    monkeypatch.setattr(serve_route, "head_etag", lambda key: _async('"e"'))
    monkeypatch.setattr(serve_route, "download_artifact", lambda key: _async(fake_bytes))

    response = await client.get("/acme/post")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == fake_bytes


@pytest.mark.asyncio
async def test_serve_pdf_with_correct_mime(client, db, monkeypatch):
    await _make_deployment(db, content_type="application/pdf")

    fake_bytes = b"%PDF-1.4"
    monkeypatch.setattr(serve_route, "head_etag", lambda key: _async('"e"'))
    monkeypatch.setattr(serve_route, "download_artifact", lambda key: _async(fake_bytes))

    response = await client.get("/acme/post")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content == fake_bytes


@pytest.mark.asyncio
async def test_serve_uses_etag_cache(client, db, monkeypatch):
    await _make_deployment(db, content_type="text/markdown")
    downloads = 0

    async def fake_etag(key: str) -> str:
        return '"stable"'

    async def fake_download(key: str) -> bytes:
        nonlocal downloads
        downloads += 1
        return b"# Cached"

    monkeypatch.setattr(serve_route, "head_etag", fake_etag)
    monkeypatch.setattr(serve_route, "download_artifact", fake_download)

    first = await client.get("/acme/post")
    second = await client.get("/acme/post")

    assert first.status_code == second.status_code == 200
    # Same ETag both times, so the second request serves from the cache.
    assert downloads == 1


@pytest.mark.asyncio
async def test_serve_404_when_not_uploaded(client, db, monkeypatch):
    await _make_deployment(db, content_type="text/markdown")

    async def fake_etag(key: str) -> None:
        return None

    monkeypatch.setattr(serve_route, "head_etag", fake_etag)

    response = await client.get("/acme/post")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_serve_404_for_unknown_workspace(client, db):
    response = await client.get("/nope/whatever")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_serve_pending_row_404s_when_not_uploaded(client, db, monkeypatch):
    await _make_deployment(db, content_type="text/markdown", status="pending")

    async def fake_head(key: str) -> None:
        return None

    # The serve path's lazy reconcile uses the service-layer HEAD.
    monkeypatch.setattr(deployment_service, "head_etag", fake_head)

    response = await client.get("/acme/post")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_serve_pending_row_reconciles_and_serves(client, db, monkeypatch):
    await _make_deployment(db, content_type="text/markdown", status="pending")

    async def present_head(key: str) -> str:
        return '"etag-1"'

    async def fake_download(key: str) -> bytes:
        return b"# Title"

    # Object is present, so the reconcile promotes the row and serve renders it.
    monkeypatch.setattr(deployment_service, "head_etag", present_head)
    monkeypatch.setattr(serve_route, "head_etag", present_head)
    monkeypatch.setattr(serve_route, "download_artifact", fake_download)

    response = await client.get("/acme/post")

    assert response.status_code == 200
    assert "<h1>Title</h1>" in response.text


@pytest.mark.asyncio
async def test_instructions_endpoint(client):
    response = await client.get("/v1/instructions")

    assert response.status_code == 200
    assert "text/markdown" in response.headers["content-type"]
    assert "Ship Deployment Guide" in response.text


async def _async(value):
    return value
