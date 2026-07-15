"""MCP streamable-HTTP server exposing the deploy/list/delete tools.

The tools reuse the same service layer as the REST routes and authenticate with
the same ``sk_live_`` bearer tokens. Because MCP tools aren't FastAPI routes,
they can't use the ``require_api_key`` dependency directly: instead each tool
reads the ``Authorization`` header off the request carried in the MCP request
context and resolves it through the shared :func:`resolve_api_key` helper.
"""

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from ..auth import WorkspaceContext, resolve_api_key
from ..config import settings
from ..database import SessionLocal
from ..instructions import agent_upload_guide
from ..services import deployments as deployment_service

_INSTRUCTIONS = """\
Undocking publishes LLM-generated artifacts (HTML, Markdown, images, PDFs, JSON,
SVG, CSV, plain text) to permanent public URLs. Use these tools whenever the user
asks to publish, undock, deploy, share, host, or put an artifact online — e.g.
"publish this report", "undock this page", "share this as a link", "put this
online". Use `deploy_artifact` for text up to 1 MB and `create_upload_url` for
binary files or anything larger. All tools talk directly to the Undocking API.
"""

# The app is mounted at the root in main.py, so streamable_http_path="/mcp"
# registers a plain Route at exactly "/mcp" — a sub-path mount would 307 the
# bare "/mcp" to "/mcp/", which many MCP clients refuse to follow.
#
# DNS-rebinding protection must be disabled *explicitly*: when the argument is
# omitted, FastMCP auto-enables it with a localhost-only allowlist and rejects
# every non-local Host with a 421. Agents connect directly from anywhere, so
# the endpoint accepts any Host/Origin; auth is the bearer key on each call.
mcp = FastMCP(
    "undocking",
    streamable_http_path="/mcp",
    instructions=_INSTRUCTIONS,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


class _AuthError(Exception):
    """Raised when an MCP request carries no valid bearer token."""


def _bearer_token(ctx: Context) -> str:
    """Extracts the raw bearer token from the request behind an MCP call.

    Raises:
        _AuthError: If there is no request or no ``Bearer`` Authorization header.
    """
    request = ctx.request_context.request
    if request is None:
        raise _AuthError("No request context available")

    authorization = request.headers.get("authorization", "")
    if not authorization.startswith("Bearer "):
        raise _AuthError("Missing Authorization header")
    return authorization[7:]


def _deployment_url(workspace: WorkspaceContext, slug: str) -> str:
    return f"{settings.public_base_url}/{workspace.workspace_slug}/{slug}"


@mcp.tool()
async def deploy_artifact(
    ctx: Context,
    content: str,
    content_type: str,
    slug: str | None = None,
) -> dict:
    """Publish (a.k.a. "undock") a text artifact to a public URL. Returns a live URL immediately.

    Use this whenever the user says "publish X", "undock X", "deploy X",
    "share X as a link", or "put X online" and the artifact is text ≤ 1 MB.

    ``content_type`` must be one of: text/html, text/markdown, text/plain,
    text/csv, application/json, image/svg+xml.

    For binary files (image/png, image/jpeg, image/gif, image/webp,
    application/pdf) or content > 1 MB, use ``create_upload_url`` instead.
    """
    async with SessionLocal() as db:
        try:
            workspace = await resolve_api_key(_bearer_token(ctx), db)
        except _AuthError as error:
            return {"error": str(error)}
        if workspace is None:
            return {"error": "Invalid or revoked API key"}

        try:
            deployment = await deployment_service.create_inline_deployment(
                db,
                workspace,
                content_type=content_type,
                slug=slug,
                content=content,
            )
        except deployment_service.SlugTakenError as error:
            return {"error": f'Slug "{error}" is already taken in this workspace'}

        return {
            "id": str(deployment.id),
            "url": _deployment_url(workspace, deployment.slug),
            "status": deployment.status,
        }


@mcp.tool()
async def create_upload_url(
    ctx: Context,
    content_type: str,
    slug: str | None = None,
) -> dict:
    """Reserve a presigned PUT URL to publish ("undock") any artifact type, including binary files.

    Use this when the user wants to publish, undock, deploy, or share an image,
    PDF, or any artifact over 1 MB.

    ``content_type`` must be one of: text/html, text/markdown, text/plain,
    text/csv, application/json, image/svg+xml, image/png, image/jpeg,
    image/gif, image/webp, application/pdf.

    The returned ``upload_url`` accepts a plain PUT with the artifact bytes.
    You MUST send ``Content-Type: <content_type>`` as a header on the PUT.
    Status is ``"pending"`` until the upload lands; poll ``list_deployments`` to watch.
    """
    async with SessionLocal() as db:
        try:
            workspace = await resolve_api_key(_bearer_token(ctx), db)
        except _AuthError as error:
            return {"error": str(error)}
        if workspace is None:
            return {"error": "Invalid or revoked API key"}

        try:
            deployment, upload_url = await deployment_service.reserve_upload(
                db,
                workspace,
                content_type=content_type,
                slug=slug,
            )
        except deployment_service.SlugTakenError as error:
            return {"error": f'Slug "{error}" is already taken in this workspace'}

        return {
            "id": str(deployment.id),
            "url": _deployment_url(workspace, deployment.slug),
            "upload_url": upload_url,
            "expires_in": settings.upload_url_expiry_seconds,
            "method": "PUT",
            "content_type": content_type,
            "status": deployment.status,
        }


@mcp.tool()
async def list_deployments(ctx: Context, limit: int = 50) -> dict:
    """List the workspace's published (undocked) artifacts, newest first."""
    async with SessionLocal() as db:
        try:
            workspace = await resolve_api_key(_bearer_token(ctx), db)
        except _AuthError as error:
            return {"error": str(error)}
        if workspace is None:
            return {"error": "Invalid or revoked API key"}

        deployments = await deployment_service.list_deployments(db, workspace, limit=limit)
        return {
            "deployments": [
                {
                    "id": str(deployment.id),
                    "slug": deployment.slug,
                    "content_type": deployment.content_type,
                    "status": deployment.status,
                    "created_at": deployment.created_at.isoformat(),
                    "url": _deployment_url(workspace, deployment.slug),
                }
                for deployment in deployments
            ]
        }


@mcp.tool()
async def delete_deployment(ctx: Context, deployment_id: str) -> dict:
    """Soft-delete a published (undocked) artifact by deployment ID; its public URL stops serving."""
    async with SessionLocal() as db:
        try:
            workspace = await resolve_api_key(_bearer_token(ctx), db)
        except _AuthError as error:
            return {"error": str(error)}
        if workspace is None:
            return {"error": "Invalid or revoked API key"}

        try:
            await deployment_service.delete_deployment(db, workspace, deployment_id)
        except deployment_service.DeploymentNotFoundError:
            return {"error": "Deployment not found"}

        return {"deleted": deployment_id}


@mcp.prompt()
def how_to_deploy() -> str:
    """Full guide: deploy any artifact and get a public URL."""
    return agent_upload_guide()


@mcp.resource("undocking://guide/deploy", mime_type="text/markdown")
def deploy_guide() -> str:
    """The Undocking deployment guide for agents."""
    return agent_upload_guide()
