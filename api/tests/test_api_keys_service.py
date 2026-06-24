import uuid

import pytest

from ship_api.auth import create_api_key, resolve_api_key
from ship_api.models import User, Workspace
from ship_api.services import api_keys as service


async def _workspace(db, slug: str = "acme") -> Workspace:
    user = User(email=f"{uuid.uuid4()}@example.com", name="Owner")
    db.add(user)
    await db.flush()
    workspace = Workspace(slug=slug, name="Acme", owner_id=user.id)
    db.add(workspace)
    await db.commit()
    await db.refresh(workspace)
    return workspace


@pytest.mark.asyncio
async def test_create_api_key_returns_resolvable_token(db):
    workspace = await _workspace(db)

    key, raw = await create_api_key(db, str(workspace.id), "default")

    assert raw.startswith("sk_live_")
    assert key.key_prefix == raw[:16]
    context = await resolve_api_key(raw, db)
    assert context is not None
    assert context.workspace_id == str(workspace.id)


@pytest.mark.asyncio
async def test_list_api_keys_scoped_to_workspace(db):
    workspace_a = await _workspace(db, "a")
    workspace_b = await _workspace(db, "b")
    await create_api_key(db, str(workspace_a.id), "a-key")

    assert await service.list_api_keys(db, workspace_b.id) == []
    assert len(await service.list_api_keys(db, workspace_a.id)) == 1


@pytest.mark.asyncio
async def test_revoke_api_key_disables_token(db):
    workspace = await _workspace(db)
    key, raw = await create_api_key(db, str(workspace.id), "default")

    await service.revoke_api_key(db, workspace.id, str(key.id))

    assert await resolve_api_key(raw, db) is None


@pytest.mark.asyncio
async def test_revoke_api_key_enforces_workspace_isolation(db):
    owner = await _workspace(db, "owner")
    intruder = await _workspace(db, "intruder")
    key, _ = await create_api_key(db, str(owner.id), "default")

    with pytest.raises(service.ApiKeyNotFoundError):
        await service.revoke_api_key(db, intruder.id, str(key.id))


@pytest.mark.asyncio
async def test_revoke_api_key_raises_for_unknown_id(db):
    workspace = await _workspace(db)

    with pytest.raises(service.ApiKeyNotFoundError):
        await service.revoke_api_key(db, workspace.id, str(uuid.uuid4()))
