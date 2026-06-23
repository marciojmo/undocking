from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .logging_config import configure_logging
from .mcp.server import mcp
from .routes.deployments import router as deployments_router
from .routes.serve import router as serve_router

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # The MCP streamable-HTTP transport needs its session manager running for
    # the lifetime of the app; share its lifespan with FastAPI's.
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="Ship API", lifespan=lifespan)
app.include_router(deployments_router)
app.mount("/mcp", mcp.streamable_http_app())

# Mounted last: its catch-all "/{workspace_slug}/{slug}" must not shadow the
# /v1 and /mcp routes registered above.
app.include_router(serve_router)
