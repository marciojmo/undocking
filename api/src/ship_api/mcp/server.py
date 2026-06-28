"""MCP streamable-HTTP server exposing the deploy/list/delete tools.

The tools reuse the same service layer as the REST routes and authenticate with
the same ``sk_live_`` bearer tokens. Because MCP tools aren't FastAPI routes,
they can't use the ``require_api_key`` dependency directly: instead each tool
reads the ``Authorization`` header off the request carried in the MCP request
context and resolves it through the shared :func:`resolve_api_key` helper.
"""

from mcp.server.fastmcp import Context, FastMCP

from ..auth import WorkspaceContext, resolve_api_key
from ..config import settings
from ..database import SessionLocal
from ..instructions import agent_upload_guide
from ..services import deployments as deployment_service

# streamable_http_path is set to "/" so that, once mounted at "/mcp" in main.py,
# the endpoint is served at "/mcp" rather than the doubled-up "/mcp/mcp".
mcp = FastMCP("ship", streamable_http_path="/")


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
    """Deploy a text artifact inline (≤ 1 MB). Returns a live URL immediately.

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
    """Reserve a presigned PUT URL for any artifact type, including binary files.

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
    """List workspace deployments, newest first."""
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
    """Soft-delete a deployment by ID."""
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


@mcp.resource("ship://guide/deploy", mime_type="text/markdown")
def deploy_guide() -> str:
    """The Ship deployment guide for agents."""
    return agent_upload_guide()
