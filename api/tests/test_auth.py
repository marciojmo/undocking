import uuid
from datetime import UTC, datetime

import pytest

from ship_api import auth
from ship_api.models import ApiKey, User, Workspace

VALID_TOKEN = "sk_live_abcdef0123456789xyz"


async def _seed_key(db, token: str = VALID_TOKEN, revoked: bool = False) -> Workspace:
    user = User(email=f"{uuid.uuid4()}@example.com", name="Owner")
    db.add(user)
    await db.flush()

    workspace = Workspace(slug="acme", name="Acme", owner_id=user.id)
    db.add(workspace)
    await db.flush()

    db.add(
        ApiKey(
            workspace_id=workspace.id,
            key_hash=auth._sha256(token),
            key_prefix=token[:16],
            name="default",
            revoked_at=datetime.now(UTC) if revoked else None,
        )
    )
    await db.commit()
    return workspace


@pytest.mark.asyncio
async def test_resolve_api_key_returns_context_for_valid_token(db):
    workspace = await _seed_key(db)

    context = await auth.resolve_api_key(VALID_TOKEN, db)

    assert context is not None
    assert context.workspace_id == str(workspace.id)
    assert context.workspace_slug == "acme"


@pytest.mark.asyncio
async def test_resolve_api_key_rejects_unknown_token(db):
    await _seed_key(db)

    assert await auth.resolve_api_key("sk_live_unknownunknown00", db) is None


@pytest.mark.asyncio
async def test_resolve_api_key_rejects_revoked_token(db):
    await _seed_key(db, revoked=True)

    assert await auth.resolve_api_key(VALID_TOKEN, db) is None


@pytest.mark.asyncio
async def test_resolve_api_key_rejects_wrong_prefix_scheme(db):
    await _seed_key(db)

    assert await auth.resolve_api_key("nope_not_a_real_key_value", db) is None


@pytest.mark.asyncio
async def test_resolve_api_key_rejects_too_short_token(db):
    assert await auth.resolve_api_key("sk_live_short", db) is None
