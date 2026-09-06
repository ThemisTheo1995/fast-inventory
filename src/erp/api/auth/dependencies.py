from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Cookie, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.api.auth.exceptions import CredentialsExceptionError
from erp.api.auth.models import User
from erp.api.workspace_user.enums import InvitationStatusEnum
from erp.api.workspace_user.exceptions import WorkspaceUserNotFoundError
from erp.api.workspace_user.models import WorkspaceUser
from erp.core.config import get_settings
from erp.database.base import get_db

settings = get_settings()

SECRET_KEY = settings.AUTH_SECRET_KEY
ALGORITHM = settings.AUTH_ALGORITHM


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)], access_token: Annotated[str | None, Cookie()] = None
) -> User:

    if not access_token:
        raise CredentialsExceptionError()

    try:
        payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])

        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")

        if user_id is None or token_type != "access":
            raise CredentialsExceptionError()

    except jwt.PyJWTError:
        raise CredentialsExceptionError() from None

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise CredentialsExceptionError()

    return user


async def get_current_workspace_user(
    workspace_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WorkspaceUser:

    query = select(WorkspaceUser).where(
        WorkspaceUser.user_id == current_user.id,
        WorkspaceUser.workspace_id == workspace_id,
        WorkspaceUser.status == InvitationStatusEnum.ACTIVE,
        WorkspaceUser.is_deleted.is_(False),
    )

    result = await db.execute(query)
    workspace_user = result.scalar_one_or_none()

    if not workspace_user:
        raise WorkspaceUserNotFoundError()

    return workspace_user
