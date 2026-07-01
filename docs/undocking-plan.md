# Undocking API — Python Implementation Plan

## What this is

A deployment platform for HTML/Markdown artifacts. Users upload content via REST or MCP, get back a public URL, and the content is served at `/{workspace}/{slug}`. Auth is via bearer API keys scoped to a workspace. Designed for AI Agents.

### Upload model

Deploying is split into two flows, each with REST + MCP parity:

- **Inline deploy** — `POST /v1/deployments` (MCP `deploy_artifact`) carries the
  raw `content` in the request, stores it, and returns a row with
  `status: "deployed"`. The URL is live immediately. Inline content is capped at
  ~1 MB; use the presigned flow for anything larger.
- **Presigned upload** — `POST /v1/uploads` (MCP `create_upload_url`) reserves
  the slug, inserts a `status: "pending"` row, and returns a presigned R2 PUT
  `upload_url`. The caller uploads the raw bytes straight to the bucket, keeping
  large bodies out of the model's token stream and off the API. There is **no
  confirm call**: the deployment flips to `deployed` when the upload lands.

Completion is detected server-side from an **R2 event notification**. R2
delivers object events through a Cloudflare Queue; a small consumer/Worker
(configured in Cloudflare, not this repo) forwards them to the internal
`POST /internal/r2-events` webhook, authenticated by a shared secret
(`R2_EVENT_SECRET`, constant-time compared) rather than an API key. The webhook
looks the deployment up by `storage_key` and marks it `deployed` idempotently;
it tolerates single or batched events and ignores unrelated keys. As a fallback
for missed/delayed events, the serve path lazily `HEAD`s a `pending` object and
promotes it if the bytes are already present. A `pending` slug serves `404`
until it goes live.

Either way the stored object is the **raw** HTML or Markdown under
`{workspace_id}/{slug}/source`. Rendering (Markdown -> sanitized, styled HTML;
HTML body -> styled wrapper) happens at serve time, cached per object by ETag.
The agent-facing upload guide lives in [`agent-upload-guide.md`](agent-upload-guide.md)
and is served at `GET /v1/instructions` plus the MCP `how_to_deploy` prompt and
`undocking://guide/deploy` resource.

---

## Project layout

Each module has a single responsibility (no `utils.py` / `helpers.py` dumping
grounds). Business logic lives in a `services/` layer so the REST routes and the
MCP tools share one implementation of deploy/list/delete instead of duplicating
it. A `src/` layout makes the importable package name (`undocking_api`) explicit and
matches the run command.

```
undocking/
├── web/                          # Next.js admin panel (phase 2)
└── api/                          # FastAPI backend
    ├── pyproject.toml            # Dependencies + tooling config
    ├── README.md
    ├── .env.example              # Documents required settings
    └── src/
        └── undocking_api/
            ├── __init__.py
            ├── main.py           # FastAPI app, mounts routers + MCP
            ├── config.py         # Settings (pydantic-settings, reads .env)
            ├── logging_config.py # configure_logging() — stdlib logging setup
            ├── database.py       # Async SQLAlchemy engine + get_db dependency
            ├── models.py         # ORM models matching the existing schema
            ├── schemas.py        # Pydantic request/response models
            ├── auth.py           # require_api_key dependency + WorkspaceContext
            ├── storage.py        # R2 upload / download via boto3
            ├── slug.py           # generate_slug / sanitize_slug
            ├── markdown.py       # render_markdown / wrap_html
            ├── services/
            │   ├── __init__.py
            │   └── deployments.py # Shared deploy/list/delete logic (REST + MCP)
            ├── routes/
            │   ├── __init__.py
            │   ├── deployments.py # POST/GET/DELETE /v1/deployments
            │   └── serve.py       # GET /{workspace}/{slug}
            └── mcp/
                ├── __init__.py
                └── server.py      # /mcp — MCP streamable-HTTP endpoint
```

---

## Dependencies

```toml
# pyproject.toml
fastapi>=0.115
uvicorn[standard]>=0.30
pydantic>=2.7
pydantic-settings>=2.3
sqlalchemy[asyncio]>=2.0
asyncpg>=0.29
boto3>=1.34           # R2 is S3-compatible; run in threadpool
markdown-it-py>=3.0   # Markdown rendering
nh3>=0.2              # HTML sanitization (Rust-backed, fast)
mcp>=1.0              # MCP Python SDK
```

---

## config.py

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    r2_account_id: str
    r2_access_key_id: str
    r2_secret_access_key: str
    r2_bucket_name: str = "undocking-artifacts"
    r2_public_url: str
    public_base_url: str = "http://localhost:8000"
    port: int = 8000

settings = Settings()
```

---

## database.py

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from .config import settings

engine = create_async_engine(settings.database_url.replace("postgresql://", "postgresql+asyncpg://"))
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db():
    async with SessionLocal() as session:
        yield session
```

---

## models.py

Map the existing schema directly — no migrations, no changes to table names or columns.

```python
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str]
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    plan: Mapped[str] = mapped_column(default="free")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

class ApiKey(Base):
    __tablename__ = "api_keys"
    __table_args__ = (Index("api_keys_prefix_idx", "key_prefix"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"))
    key_hash: Mapped[str]
    key_prefix: Mapped[str]
    name: Mapped[str]
    revoked_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

class Deployment(Base):
    __tablename__ = "deployments"
    __table_args__ = (UniqueConstraint("workspace_id", "slug"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"))
    slug: Mapped[str]
    content_type: Mapped[str]       # "html" | "markdown"
    storage_key: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    deleted_at: Mapped[datetime | None]
```

---

## auth.py

```python
import hashlib
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .models import ApiKey, Workspace

def _sha256(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

@dataclass(frozen=True)
class WorkspaceContext:
    """The workspace and API key resolved from a request's bearer token."""

    workspace_id: str
    workspace_slug: str
    api_key_id: str

async def resolve_api_key(token: str, db: AsyncSession) -> WorkspaceContext | None:
    """Resolves a bearer token to a workspace, or None if it's invalid.

    Transport-agnostic so the REST dependency and the MCP server share one
    implementation.

    Args:
        token: The raw API key (without the ``Bearer `` prefix).
        db: Async database session.

    Returns:
        The workspace context the key is scoped to, or None when the token is
        malformed, unknown, or revoked.
    """
    if not token.startswith("sk_live_") or len(token) < 20:
        return None

    prefix = token[:16]
    key_hash = _sha256(token)

    row = (await db.execute(
        select(ApiKey.id, ApiKey.revoked_at, Workspace.id, Workspace.slug)
        .join(Workspace, ApiKey.workspace_id == Workspace.id)
        .where(ApiKey.key_prefix == prefix, ApiKey.key_hash == key_hash)
        .limit(1)
    )).first()

    if not row or row.revoked_at:
        return None

    return WorkspaceContext(str(row[2]), row[3], str(row[0]))

async def require_api_key(
    authorization: Annotated[str, Header()],
    db: AsyncSession = Depends(get_db),
) -> WorkspaceContext:
    """FastAPI dependency that resolves the bearer token, raising 401 if invalid.

    Args:
        authorization: The raw ``Authorization`` request header.
        db: Async database session.

    Returns:
        The workspace context the API key is scoped to.

    Raises:
        HTTPException: 401 if the header is missing, malformed, or the key
            is unknown or revoked.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing Authorization header")

    workspace = await resolve_api_key(authorization[7:], db)
    if workspace is None:
        raise HTTPException(401, "Invalid or revoked API key")
    return workspace
```

---

## storage.py

Run boto3 calls in a threadpool — it's synchronous but fast enough.

```python
import asyncio
import boto3
from .config import settings

_client = boto3.client(
    "s3",
    region_name="auto",
    endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
    aws_access_key_id=settings.r2_access_key_id,
    aws_secret_access_key=settings.r2_secret_access_key,
)

def _upload(key: str, html: str) -> None:
    _client.put_object(
        Bucket=settings.r2_bucket_name,
        Key=key,
        Body=html.encode(),
        ContentType="text/html; charset=utf-8",
        CacheControl="public, max-age=31536000, immutable",
    )

def _download(key: str) -> str | None:
    try:
        res = _client.get_object(Bucket=settings.r2_bucket_name, Key=key)
        return res["Body"].read().decode()
    except _client.exceptions.NoSuchKey:
        return None

async def upload_artifact(key: str, html: str) -> None:
    await asyncio.get_event_loop().run_in_executor(None, _upload, key, html)

async def download_artifact(key: str) -> str | None:
    return await asyncio.get_event_loop().run_in_executor(None, _download, key)
```

---

## slug.py

```python
import re
import secrets
import string

_ALPHABET = string.ascii_lowercase + string.digits

def generate_slug(length: int = 10) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))

def sanitize_slug(raw: str) -> str:
    slug = re.sub(r"[^a-z0-9-]", "-", raw.lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:64]
```

---

## markdown.py

```python
import nh3
from markdown_it import MarkdownIt

_md = MarkdownIt()

_EXTRA_TAGS = {"h1","h2","h3","h4","h5","h6","img","video","source","details","summary","mark","del","ins","kbd","sup","sub"}

def render_markdown(content: str) -> str:
    raw = _md.render(content)
    safe = nh3.clean(raw, tags=nh3.ALLOWED_TAGS | _EXTRA_TAGS)
    return wrap_html(safe)

def wrap_html(body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<style>
  *, *::before, *::after {{ box-sizing: border-box; }}
  body {{ margin: 0 auto; max-width: 800px; padding: 2rem 1.5rem; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 1rem; line-height: 1.7; color: #1a1a1a; background: #fff; }}
  h1, h2, h3, h4, h5, h6 {{ line-height: 1.3; margin: 1.5em 0 0.5em; }}
  h1 {{ font-size: 2rem; }} h2 {{ font-size: 1.5rem; }}
  a {{ color: #0070f3; }}
  pre {{ background: #f4f4f5; padding: 1rem; border-radius: 6px; overflow-x: auto; }}
  code {{ font-family: "Fira Code", Consolas, monospace; font-size: 0.9em; }}
  pre code {{ background: none; }}
  code:not(pre code) {{ background: #f4f4f5; padding: 0.1em 0.3em; border-radius: 3px; }}
  blockquote {{ border-left: 4px solid #e5e7eb; margin: 0; padding-left: 1rem; color: #6b7280; }}
  img {{ max-width: 100%; height: auto; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #e5e7eb; padding: 0.5rem 0.75rem; text-align: left; }}
  th {{ background: #f9fafb; font-weight: 600; }}
</style>
</head>
<body>
{body}
</body>
</html>"""
```

---

## schemas.py

Request/response models live here so routes stay thin and the same shapes can be
reused by the MCP tools.

```python
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

class DeployRequest(BaseModel):
    content: str = Field(min_length=1, max_length=5_000_000)
    content_type: Literal["html", "markdown"]
    slug: str | None = Field(default=None, min_length=1, max_length=64)

class DeployResponse(BaseModel):
    id: str
    url: str

class DeploymentItem(BaseModel):
    id: str
    slug: str
    content_type: str
    created_at: datetime
    url: str
```

---

## services/deployments.py

The single source of truth for deploy/list/delete. Both the REST routes and the
MCP tools call these functions; the service raises domain-specific exceptions and
lets each transport translate them (HTTP status codes for REST, error payloads
for MCP).

```python
import logging
import uuid
from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import WorkspaceContext
from ..markdown import render_markdown, wrap_html
from ..models import Deployment
from ..slug import generate_slug, sanitize_slug
from ..storage import upload_artifact

logger = logging.getLogger(__name__)

class SlugTakenError(Exception):
    """Raised when an explicitly requested slug already exists in the workspace."""

class DeploymentNotFoundError(Exception):
    """Raised when no active deployment matches the given ID."""

async def create_deployment(
    db: AsyncSession,
    workspace: WorkspaceContext,
    content: str,
    content_type: str,
    slug: str | None = None,
) -> Deployment:
    """Renders content, uploads it to R2, and records the deployment.

    The deployment is always bound to ``workspace`` — the target workspace is
    taken solely from the authenticated context, never from caller input, so a
    caller cannot create content in another workspace.

    Args:
        db: Async database session.
        workspace: The authenticated workspace.
        content: Raw HTML or Markdown to publish.
        content_type: Either "html" or "markdown".
        slug: Optional caller-supplied slug; a random one is generated when omitted.

    Returns:
        The persisted deployment.

    Raises:
        SlugTakenError: If an explicit slug is already used in the workspace.
    """
    requested_slug = sanitize_slug(slug) if slug else generate_slug()

    if await _slug_exists(db, workspace.workspace_id, requested_slug):
        if slug:
            raise SlugTakenError(requested_slug)
        requested_slug = generate_slug()

    html = render_markdown(content) if content_type == "markdown" else wrap_html(content)
    storage_key = f"{workspace.workspace_id}/{requested_slug}/index.html"
    await upload_artifact(storage_key, html)

    deployment = Deployment(
        workspace_id=workspace.workspace_id,
        slug=requested_slug,
        content_type=content_type,
        storage_key=storage_key,
    )
    db.add(deployment)
    await db.commit()
    await db.refresh(deployment)
    logger.info("Deployed %s to workspace %s", deployment.id, workspace.workspace_slug)
    return deployment

async def list_deployments(
    db: AsyncSession,
    workspace: WorkspaceContext,
    limit: int = 50,
) -> list[Deployment]:
    """Returns the workspace's active deployments, newest first."""
    result = await db.execute(
        select(Deployment)
        .where(
            Deployment.workspace_id == workspace.workspace_id,
            Deployment.deleted_at.is_(None),
        )
        .order_by(desc(Deployment.created_at))
        .limit(limit)
    )
    return list(result.scalars().all())

async def delete_deployment(
    db: AsyncSession,
    workspace: WorkspaceContext,
    deployment_id: str,
) -> None:
    """Soft-deletes a deployment owned by the authenticated workspace.

    IDs are accepted as strings so every transport (REST path params, MCP tool
    arguments) can pass them uniformly without a UUID type. A value that isn't a
    valid UUID can't match any row, so it's treated as not found rather than
    surfacing a database error.

    The query is scoped to ``workspace`` as well as the ID, so a deployment that
    belongs to another workspace is treated as not found rather than deleted —
    this both enforces isolation and avoids revealing that the ID exists
    elsewhere.

    Raises:
        DeploymentNotFoundError: If ``deployment_id`` isn't a valid UUID, or no
            active deployment with this ID exists in the workspace.
    """
    try:
        parsed_id = uuid.UUID(deployment_id)
    except ValueError:
        raise DeploymentNotFoundError(deployment_id)

    result = await db.execute(
        select(Deployment)
        .where(
            Deployment.id == parsed_id,
            Deployment.workspace_id == workspace.workspace_id,
            Deployment.deleted_at.is_(None),
        )
        .limit(1)
    )
    deployment = result.scalar_one_or_none()
    if deployment is None:
        raise DeploymentNotFoundError(deployment_id)

    deployment.deleted_at = datetime.utcnow()
    await db.commit()

async def _slug_exists(db: AsyncSession, workspace_id: str, slug: str) -> bool:
    result = await db.execute(
        select(Deployment.id)
        .where(
            Deployment.workspace_id == workspace_id,
            Deployment.slug == slug,
            Deployment.deleted_at.is_(None),
        )
        .limit(1)
    )
    return result.first() is not None
```

---

## routes/deployments.py

Thin HTTP handlers: validate input, call the service, translate domain errors.
All deployment endpoints share one router since they act on the same resource.

```python
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_api_key, WorkspaceContext
from ..config import settings
from ..database import get_db
from ..schemas import DeployRequest, DeployResponse, DeploymentItem
from ..services import deployments as deployment_service

router = APIRouter(prefix="/v1", tags=["deployments"])

@router.post("/deployments", response_model=DeployResponse, status_code=201)
async def create_deployment(
    body: DeployRequest,
    workspace: Annotated[WorkspaceContext, Depends(require_api_key)],
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> DeployResponse:
    """Creates a deployment from an HTML or Markdown artifact and returns its public URL."""
    try:
        deployment = await deployment_service.create_deployment(
            db,
            workspace,
            content=body.content,
            content_type=body.content_type,
            slug=body.slug,
        )
    except deployment_service.SlugTakenError as error:
        raise HTTPException(409, f'Slug "{error}" is already taken in this workspace')

    url = f"{settings.public_base_url}/{workspace.workspace_slug}/{deployment.slug}"
    response.headers["Location"] = url
    return DeployResponse(id=str(deployment.id), url=url)

@router.get("/deployments", response_model=list[DeploymentItem])
async def list_deployments(
    workspace: Annotated[WorkspaceContext, Depends(require_api_key)],
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[DeploymentItem]:
    """Lists the workspace's active deployments, newest first."""
    deployments = await deployment_service.list_deployments(db, workspace, limit=limit)
    base = settings.public_base_url
    return [
        DeploymentItem(
            id=str(deployment.id),
            slug=deployment.slug,
            content_type=deployment.content_type,
            created_at=deployment.created_at,
            url=f"{base}/{workspace.workspace_slug}/{deployment.slug}",
        )
        for deployment in deployments
    ]

@router.delete("/deployments/{deployment_id}", status_code=204)
async def delete_deployment(
    deployment_id: str,
    workspace: Annotated[WorkspaceContext, Depends(require_api_key)],
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-deletes a deployment by ID. Returns 204 No Content on success."""
    try:
        await deployment_service.delete_deployment(db, workspace, deployment_id)
    except deployment_service.DeploymentNotFoundError:
        raise HTTPException(404, "Deployment not found")
```

---

## routes/serve.py

```python
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, JSONResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Deployment, Workspace
from ..storage import download_artifact

router = APIRouter()

@router.get("/{workspace_slug}/{slug}")
async def serve(
    workspace_slug: str,
    slug: str,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Serves a deployed artifact's HTML, or a JSON error for missing/expired ones."""
    workspace = (await db.execute(
        select(Workspace).where(Workspace.slug == workspace_slug).limit(1)
    )).scalar_one_or_none()
    if not workspace:
        return JSONResponse({"error": "Not found"}, 404)

    deployment = (await db.execute(
        select(Deployment)
        .where(Deployment.workspace_id == workspace.id, Deployment.slug == slug, Deployment.deleted_at.is_(None))
        .limit(1)
    )).scalar_one_or_none()
    if not deployment:
        return JSONResponse({"error": "Not found"}, 404)

    html = await download_artifact(deployment.storage_key)
    if not html:
        return JSONResponse({"error": "Not found"}, 404)

    return HTMLResponse(html)
```

---

## mcp/server.py

Use the MCP Python SDK's `FastMCP` class, which integrates directly with a FastAPI/Starlette app and handles the Streamable HTTP transport.

```python
from mcp.server.fastmcp import FastMCP
from ..auth import resolve_api_key   # shared helper returning WorkspaceContext | None
from ..services import deployments as deployment_service  # same logic as the REST routes

mcp = FastMCP("undocking")

@mcp.tool()
async def deploy_artifact(content: str, content_type: str, slug: str | None = None) -> dict:
    """Deploy an HTML or Markdown artifact and get back a public URL."""
    ...

@mcp.tool()
async def list_deployments(limit: int = 50) -> dict:
    """List deployments in the current workspace."""
    ...

@mcp.tool()
async def delete_deployment(deployment_id: str) -> dict:
    """Soft-delete a deployment by ID."""
    ...
```

Mount the MCP server as a sub-app: `app.mount("/mcp", mcp.streamable_http_app())`.

Auth for MCP: FastMCP supports a custom auth dependency — pass the same `require_api_key` function, or implement a `BearerAuthProvider` that calls `resolve_api_key`.

---

## logging_config.py

Configure stdlib logging once, at startup — never use `print` for diagnostics.

```python
import logging

def configure_logging(level: int = logging.INFO) -> None:
    """Configures root logging for the application.

    Args:
        level: Minimum level to emit. Defaults to ``logging.INFO``.
    """
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
```

---

## main.py

```python
from fastapi import FastAPI

from .logging_config import configure_logging
from .mcp.server import mcp
from .routes.deployments import router as deployments_router
from .routes.serve import router as serve_router

configure_logging()

app = FastAPI(title="Undocking API")
app.include_router(deployments_router)
app.include_router(serve_router)
app.mount("/mcp", mcp.streamable_http_app())
```

Run with: `uvicorn undocking_api.main:app --port 8000`

---

## What stays the same

- Database schema — same tables and columns, minus the fields trimmed for the MVP (see below)
- R2 storage layout — keyed by immutable workspace ID: `{workspace_id}/{slug}/source` (raw content; rendered on serve)
- Auth scheme (`sk_live_` prefix, SHA-256 hash, key_prefix index)
- API surface (`/v1/deployments`, `/{workspace}/{slug}`, `/mcp`)
- HTML wrapper and markdown rendering output

## What changes

| TypeScript | Python |
|---|---|
| `marked` | `markdown-it-py` |
| `sanitize-html` | `nh3` |
| `nanoid` | `secrets.choice` |
| `drizzle-orm` | `SQLAlchemy 2.x async` |
| `@aws-sdk/client-s3` | `boto3` (threadpool) |
| `@modelcontextprotocol/sdk` | `mcp` (FastMCP) |

---

## Deferred (not in the MVP)

Trimmed to keep the first version lean. Each is easy to add back later without reshaping the core deploy → serve flow:

- **Artifact expiry / TTL** — dropped `ttl_hours` and the `expires_at` column. Deployments live until explicitly deleted. Revisit if ephemeral previews become a future feature.
- **API key `last_used_at` tracking** — removed the per-request DB write (a query + commit on every authenticated call). Reintroduce with a throttled or background update if the dashboard needs "last used" timestamps.
- **Workspace + API key management endpoints** — signup/login, workspace creation, and key issuance live in the admin panel (phase 2, `web/`), not this agent-facing API. The API here assumes a workspace and key already exist.
