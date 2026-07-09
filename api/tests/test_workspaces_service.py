import pytest

from undocking_api.models import User
from undocking_api.services import workspaces as service


async def _user(db, email: str = "owner@example.com") -> User:
    user = User(email=email, name="Owner")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.mark.asyncio
async def test_create_workspace_derives_slug_from_name(db):
    user = await _user(db)

    workspace = await service.create_workspace(db, user.id, "My Cool Space!")

    assert workspace.slug == "my-cool-space"
    assert workspace.name == "My Cool Space!"
    assert workspace.owner_id == user.id


@pytest.mark.asyncio
async def test_create_workspace_disambiguates_taken_slug(db):
    user = await _user(db)

    first = await service.create_workspace(db, user.id, "Acme")
    second = await service.create_workspace(db, user.id, "Acme")

    assert first.slug == "acme"
    assert second.slug != first.slug
    assert second.slug.startswith("acme-")


@pytest.mark.asyncio
async def test_list_workspaces_is_scoped_to_owner(db):
    owner = await _user(db, "owner@example.com")
    other = await _user(db, "other@example.com")
    await service.create_workspace(db, owner.id, "Owned")
    await service.create_workspace(db, other.id, "Theirs")

    listed = await service.list_workspaces(db, owner.id)

    assert [w.name for w in listed] == ["Owned"]


@pytest.mark.asyncio
async def test_get_owned_workspace_enforces_ownership(db):
    owner = await _user(db, "owner@example.com")
    intruder = await _user(db, "intruder@example.com")
    workspace = await service.create_workspace(db, owner.id, "Owned")

    with pytest.raises(service.WorkspaceNotFoundError):
        await service.get_owned_workspace(db, intruder.id, str(workspace.id))


@pytest.mark.asyncio
async def test_get_owned_workspace_rejects_invalid_uuid(db):
    owner = await _user(db)

    with pytest.raises(service.WorkspaceNotFoundError):
        await service.get_owned_workspace(db, owner.id, "not-a-uuid")


@pytest.mark.asyncio
async def test_create_workspace_generates_name_and_slug_when_omitted(db):
    user = await _user(db)

    workspace = await service.create_workspace(db, user.id)

    assert workspace.name
    assert workspace.slug == workspace.name


@pytest.mark.asyncio
async def test_update_slug_changes_slug(db):
    user = await _user(db)
    workspace = await service.create_workspace(db, user.id, "Acme")

    updated = await service.update_slug(db, workspace, "new-slug")

    assert updated.slug == "new-slug"


@pytest.mark.asyncio
async def test_update_slug_is_noop_when_unchanged(db):
    user = await _user(db)
    workspace = await service.create_workspace(db, user.id, "Acme")

    updated = await service.update_slug(db, workspace, workspace.slug)

    assert updated.slug == workspace.slug


@pytest.mark.asyncio
async def test_update_slug_raises_on_conflict(db):
    user = await _user(db)
    await service.create_workspace(db, user.id, "Taken")
    workspace = await service.create_workspace(db, user.id, "Acme")

    with pytest.raises(service.WorkspaceSlugTakenError):
        await service.update_slug(db, workspace, "taken")
