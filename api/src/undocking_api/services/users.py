"""User account logic shared by the dashboard auth routes."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import User

logger = logging.getLogger(__name__)


async def upsert_user(db: AsyncSession, email: str, name: str) -> User:
    """Returns the user for ``email``, creating one on first sign-in.

    Accounts are keyed by email so a user signing in with different OAuth
    providers that share an email resolves to the same account. The name is
    refreshed from the provider on each sign-in when one is supplied.

    Args:
        db: Async database session.
        email: Verified email address from the OAuth provider.
        name: Display name from the provider; may be empty.

    Returns:
        The persisted user.
    """
    normalized = email.strip().lower()
    user = (
        await db.execute(select(User).where(User.email == normalized).limit(1))
    ).scalar_one_or_none()

    if user is None:
        user = User(email=normalized, name=name or "")
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info("Created user %s", user.id)
        return user

    if name and user.name != name:
        user.name = name
        await db.commit()
        await db.refresh(user)

    return user
