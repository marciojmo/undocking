import uuid

import pytest

from ship_api.auth import WorkspaceContext
from ship_api.services import deployments as service


@pytest.fixture(autouse=True)
def mock_storage(monkeypatch):
    """Replaces R2 access with in-memory captures so tests don't hit the network."""
    uploaded: dict[str, str | bytes] = {}

    async def fake_upload(key: str, content: str | bytes, content_type: str) -> None:
        uploaded[key] = content

    def fake_presign(key: str, content_type: str, expires_in: int) -> str:
        return f"https://upload.test/{key}?exp={expires_in}"

    async def fake_head(key: str) -> str | None:
        return '"etag"' if key in uploaded else None

    monkeypatch.setattr(service, "upload_artifact", fake_upload)
    monkeypatch.setattr(service, "generate_upload_url", fake_presign)
    monkeypatch.setattr(service, "head_etag", fake_head)
    return uploaded


def _workspace(slug: str = "acme") -> WorkspaceContext:
    return WorkspaceContext(
        workspace_id=str(uuid.uuid4()),
        workspace_slug=slug,
        api_key_id=str(uuid.uuid4()),
    )


@pytest.mark.asyncio
async def test_create_inline_deployment_stores_raw_and_is_deployed(db, mock_storage):
    workspace = _workspace()

    deployment = await service.create_inline_deployment(
        db, workspace, content_type="text/markdown", content="# Title"
    )

    assert deployment.slug
    assert deployment.content_type == "text/markdown"
    assert deployment.storage_key == f"{workspace.workspace_id}/{deployment.slug}/source"
    assert deployment.status == "deployed"
    assert deployment.deployed_at is not None
    # Stored raw — rendering happens at serve time, not here.
    assert mock_storage[deployment.storage_key] == "# Title"


@pytest.mark.asyncio
async def test_create_inline_deployment_sanitizes_explicit_slug(db, mock_storage):
    workspace = _workspace()

    deployment = await service.create_inline_deployment(
        db, workspace, content_type="text/html", slug="My Post!", content="<p>hi</p>"
    )

    assert deployment.slug == "my-post"


@pytest.mark.asyncio
async def test_create_inline_deployment_raises_when_explicit_slug_taken(db, mock_storage):
    workspace = _workspace()
    await service.create_inline_deployment(
        db, workspace, content_type="text/markdown", slug="dup", content="x"
    )

    with pytest.raises(service.SlugTakenError):
        await service.create_inline_deployment(
            db, workspace, content_type="text/markdown", slug="dup", content="y"
        )


@pytest.mark.asyncio
async def test_reserve_upload_creates_pending_row_with_url(db, mock_storage):
    workspace = _workspace()

    deployment, upload_url = await service.reserve_upload(db, workspace, content_type="image/png")

    assert deployment.status == "pending"
    assert deployment.deployed_at is None
    assert deployment.storage_key == f"{workspace.workspace_id}/{deployment.slug}/source"
    # Reserving never uploads bytes; it just hands back a URL.
    assert deployment.storage_key in upload_url
    assert mock_storage == {}


@pytest.mark.asyncio
async def test_reserve_upload_raises_when_explicit_slug_taken(db, mock_storage):
    workspace = _workspace()
    await service.reserve_upload(db, workspace, content_type="application/pdf", slug="dup")

    with pytest.raises(service.SlugTakenError):
        await service.reserve_upload(db, workspace, content_type="application/pdf", slug="dup")


@pytest.mark.asyncio
async def test_mark_deployed_promotes_pending(db, mock_storage):
    workspace = _workspace()
    deployment, _ = await service.reserve_upload(db, workspace, content_type="text/markdown")

    promoted = await service.mark_deployed(db, deployment.storage_key)

    assert promoted is not None
    assert promoted.id == deployment.id
    assert promoted.status == "deployed"
    assert promoted.deployed_at is not None


@pytest.mark.asyncio
async def test_mark_deployed_is_idempotent(db, mock_storage):
    workspace = _workspace()
    deployment, _ = await service.reserve_upload(db, workspace, content_type="text/markdown")

    first = await service.mark_deployed(db, deployment.storage_key)
    assert first is not None
    first_deployed_at = first.deployed_at

    second = await service.mark_deployed(db, deployment.storage_key)
    assert second is not None
    assert second.status == "deployed"
    # Already deployed: timestamp is untouched.
    assert second.deployed_at == first_deployed_at


@pytest.mark.asyncio
async def test_mark_deployed_unknown_key_returns_none(db, mock_storage):
    assert await service.mark_deployed(db, "does/not/exist") is None


@pytest.mark.asyncio
async def test_reconcile_if_uploaded_promotes_when_object_present(db, mock_storage):
    workspace = _workspace()
    deployment, _ = await service.reserve_upload(db, workspace, content_type="image/png")
    # Simulate the bytes having landed in storage.
    mock_storage[deployment.storage_key] = b"\x89PNG\r\n"

    reconciled = await service.reconcile_if_uploaded(db, deployment)

    assert reconciled.status == "deployed"


@pytest.mark.asyncio
async def test_reconcile_if_uploaded_leaves_pending_when_absent(db, mock_storage):
    workspace = _workspace()
    deployment, _ = await service.reserve_upload(db, workspace, content_type="text/markdown")

    reconciled = await service.reconcile_if_uploaded(db, deployment)

    assert reconciled.status == "pending"


@pytest.mark.asyncio
async def test_list_deployments_carries_status(db, mock_storage):
    workspace = _workspace()
    await service.create_inline_deployment(
        db, workspace, content_type="text/markdown", slug="live", content="x"
    )
    await service.reserve_upload(db, workspace, content_type="text/markdown", slug="waiting")

    listed = await service.list_deployments(db, workspace)

    by_slug = {d.slug: d.status for d in listed}
    assert by_slug["live"] == "deployed"
    assert by_slug["waiting"] == "pending"


@pytest.mark.asyncio
async def test_list_deployments_returns_newest_first(db, mock_storage):
    workspace = _workspace()
    first = await service.create_inline_deployment(
        db, workspace, content_type="text/markdown", slug="first", content="x"
    )
    second = await service.create_inline_deployment(
        db, workspace, content_type="text/markdown", slug="second", content="y"
    )

    listed = await service.list_deployments(db, workspace)

    slugs = [d.slug for d in listed]
    assert {first.slug, second.slug} <= set(slugs)
    assert listed[0].created_at >= listed[-1].created_at


@pytest.mark.asyncio
async def test_list_deployments_is_scoped_to_workspace(db, mock_storage):
    workspace_a = _workspace("a")
    workspace_b = _workspace("b")
    await service.create_inline_deployment(db, workspace_a, content_type="text/markdown", content="x")

    assert await service.list_deployments(db, workspace_b) == []


@pytest.mark.asyncio
async def test_delete_deployment_soft_deletes(db, mock_storage):
    workspace = _workspace()
    deployment = await service.create_inline_deployment(
        db, workspace, content_type="text/markdown", content="x"
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
    deployment = await service.create_inline_deployment(
        db, owner, content_type="text/markdown", content="x"
    )

    with pytest.raises(service.DeploymentNotFoundError):
        await service.delete_deployment(db, intruder, str(deployment.id))
