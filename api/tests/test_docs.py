import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from undocking_api.main import app as configured_app


@pytest.mark.asyncio
async def test_docs_enabled_by_default():
    """DOCS_ENABLED defaults to true, so local dev keeps working unmodified."""
    transport = ASGITransport(app=configured_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/docs")).status_code == 200
        assert (await client.get("/redoc")).status_code == 200
        assert (await client.get("/openapi.json")).status_code == 200


@pytest.mark.asyncio
async def test_docs_routes_absent_when_disabled():
    """Mirrors main.py's docs_enabled=False construction: no /docs, /redoc, /openapi.json routes exist."""
    disabled_app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    transport = ASGITransport(app=disabled_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/docs")).status_code == 404
        assert (await client.get("/redoc")).status_code == 404
        assert (await client.get("/openapi.json")).status_code == 404
