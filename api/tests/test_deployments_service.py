import uuid

import pytest

from ship_api.auth import WorkspaceContext
from ship_api.services import deployments as service


@pytest.fixture(autouse=True)
def mock_storage(monkeypatch):
    """Replaces R2 uploads with an in-memory capture so tests don't hit the network."""
    uploaded: dict[str, str] = {}

    async def fake_upload(key: str, html: str) -> None:
        uploaded[key] = html

    monkeypatch.setattr(service, "upload_artifact", fake_upload)
    return uploaded


def _workspace(slug: str = "acme") -> WorkspaceContext:
    return WorkspaceContext(
        workspace_id=str(uuid.uuid4()),
        workspace_slug=slug,
        api_key_id=str(uuid.uuid4()),
    )


@pytest.mark.asyncio
async def test_create_deployment_generates_slug_when_omitted(db, mock_storage):
    workspace = _workspace()

    deployment = await service.create_deployment(
        db, workspace, content="# Hi", content_type="markdown"
    )

    assert deployment.slug
    assert deployment.content_type == "markdown"
    assert deployment.storage_key == f"{workspace.workspace_id}/{deployment.slug}/index.html"
    assert deployment.storage_key in mock_storage


@pytest.mark.asyncio
async def test_create_deployment_sanitizes_explicit_slug(db, mock_storage):
    workspace = _workspace()

    deployment = await service.create_deployment(
        db, workspace, content="<p>hi</p>", content_type="html", slug="My Post!"
    )

    assert deployment.slug == "my-post"


@pytest.mark.asyncio
async def test_create_deployment_raises_when_explicit_slug_taken(db, mock_storage):
    workspace = _workspace()
    await service.create_deployment(
        db, workspace, content="a", content_type="markdown", slug="dup"
    )

    with pytest.raises(service.SlugTakenError):
        await service.create_deployment(
            db, workspace, content="b", content_type="markdown", slug="dup"
        )


@pytest.mark.asyncio
async def test_create_deployment_renders_markdown_into_storage(db, mock_storage):
    workspace = _workspace()

    deployment = await service.create_deployment(
        db, workspace, content="# Title", content_type="markdown"
    )

    assert "<h1>Title</h1>" in mock_storage[deployment.storage_key]


@pytest.mark.asyncio
async def test_list_deployments_returns_newest_first(db, mock_storage):
    workspace = _workspace()
    first = await service.create_deployment(
        db, workspace, content="a", content_type="markdown", slug="first"
    )
    second = await service.create_deployment(
        db, workspace, content="b", content_type="markdown", slug="second"
    )

    listed = await service.list_deployments(db, workspace)

    slugs = [d.slug for d in listed]
    assert {first.slug, second.slug} <= set(slugs)
    assert listed[0].created_at >= listed[-1].created_at


@pytest.mark.asyncio
async def test_list_deployments_is_scoped_to_workspace(db, mock_storage):
    workspace_a = _workspace("a")
    workspace_b = _workspace("b")
    await service.create_deployment(db, workspace_a, content="x", content_type="markdown")

    assert await service.list_deployments(db, workspace_b) == []


@pytest.mark.asyncio
async def test_delete_deployment_soft_deletes(db, mock_storage):
    workspace = _workspace()
    deployment = await service.create_deployment(
        db, workspace, content="x", content_type="markdown"
    )

    await service.delete_deployment(db, workspace, str(deployment.id))

    assert await service.list_deployments(db, workspace) == []


@pytest.mark.asyncio
async def test_delete_deployment_raises_for_unknown_id(db, mock_storage):
    workspace = _workspace()

    with pytest.raises(service.DeploymentNotFoundError):
        await service.delete_deployment(db, workspace, str(uuid.uuid4()))


@pytest.mark.asyncio
async def test_delete_deployment_raises_for_invalid_uuid(db, mock_storage):
    workspace = _workspace()

    with pytest.raises(service.DeploymentNotFoundError):
        await service.delete_deployment(db, workspace, "not-a-uuid")


@pytest.mark.asyncio
async def test_delete_deployment_enforces_workspace_isolation(db, mock_storage):
    owner = _workspace("owner")
    intruder = _workspace("intruder")
    deployment = await service.create_deployment(
        db, owner, content="x", content_type="markdown"
    )

    with pytest.raises(service.DeploymentNotFoundError):
        await service.delete_deployment(db, intruder, str(deployment.id))
