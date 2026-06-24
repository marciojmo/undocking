import pytest

from ship_api.services.users import upsert_user


@pytest.mark.asyncio
async def test_upsert_user_creates_on_first_sign_in(db):
    user = await upsert_user(db, email="Ada@Example.com", name="Ada")

    assert user.id is not None
    assert user.email == "ada@example.com"
    assert user.name == "Ada"


@pytest.mark.asyncio
async def test_upsert_user_is_idempotent_by_email(db):
    first = await upsert_user(db, email="ada@example.com", name="Ada")
    second = await upsert_user(db, email="ada@example.com", name="Ada Lovelace")

    assert first.id == second.id
    assert second.name == "Ada Lovelace"


@pytest.mark.asyncio
async def test_upsert_user_keeps_name_when_provider_sends_none(db):
    await upsert_user(db, email="ada@example.com", name="Ada")
    user = await upsert_user(db, email="ada@example.com", name="")

    assert user.name == "Ada"
