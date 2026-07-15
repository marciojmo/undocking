from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from .config import settings
from .logging_config import configure_logging
from .mcp.server import mcp
from .routes.admin import router as admin_router
from .routes.auth import router as auth_router
from .routes.deployments import router as deployments_router
from .routes.events import router as events_router
from .routes.serve import router as serve_router
from .routes.uploads import router as uploads_router

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # The MCP streamable-HTTP transport needs its session manager running for
    # the lifetime of the app; share its lifespan with FastAPI's.
    async with mcp.session_manager.run():
        yield


app = FastAPI(
    title="Undocking API",
    lifespan=lifespan,
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)

# Signs the dashboard session cookie used by the OAuth sign-in flow. Required by
# request.session in the auth/admin routes.
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    same_site="lax",
    https_only=False,
)

app.include_router(deployments_router)
app.include_router(uploads_router)
app.include_router(events_router)
app.include_router(auth_router)
app.include_router(admin_router)

# Its catch-all "/{workspace_slug}/{slug}" must not shadow the /v1, /auth, and
# /admin routes registered above.
app.include_router(serve_router)

# Mounted at the root (last, so every explicit route above wins) because the
# MCP app registers its endpoint at exactly "/mcp". Mounting it at a sub-path
# instead would 307-redirect the bare "/mcp" to "/mcp/", which many MCP
# clients refuse to follow.
app.mount("/", mcp.streamable_http_app())
