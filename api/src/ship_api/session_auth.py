"""Session-cookie auth for the dashboard.

Distinct from ``auth.py``: that module authenticates agents via ``sk_live_``
bearer tokens, while this one authenticates humans via the signed session cookie
set after OAuth sign-in.
"""

import uuid

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .models import User

SESSION_USER_KEY = "user_id"


def login_session(request: Request, user: User) -> None:
    """Records the signed-in user in the session cookie."""
    request.session[SESSION_USER_KEY] = str(user.id)


def logout_session(request: Request) -> None:
    """Clears the session, signing the user out."""
    request.session.clear()


async def require_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency resolving the session cookie to a user, else 401.

    Raises:
        HTTPException: 401 when the session is missing, malformed, or points at
            a user that no longer exists.
    """
    raw_id = request.session.get(SESSION_USER_KEY)
    if not raw_id:
        raise HTTPException(401, "Not authenticated")

    try:
        user_id = uuid.UUID(raw_id)
    except (ValueError, TypeError) as error:
        raise HTTPException(401, "Not authenticated") from error

    user = (
        await db.execute(select(User).where(User.id == user_id).limit(1))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(401, "Not authenticated")
    return user
