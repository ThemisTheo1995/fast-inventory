from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.future import select
from sqlalchemy.orm import Session

from erp.api.auth.exceptions import CredentialsException
from erp.api.auth.models import User
from erp.api.workspace.exceptions import WorkspaceNotFound
from erp.api.workspace.models import WorkspaceUser
from erp.core.config import get_settings
from erp.database.base import get_db

settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

SECRET_KEY = settings.AUTH_SECRET_KEY
ALGORITHM = settings.AUTH_ALGORITHM


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    token: str = Depends(oauth2_scheme)
) -> User:
    """
    Global dependency to authenticate incoming requests via Access Token.
    Validates the signature, ensures the user exists, and checks session validity.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")

        if user_id is None or token_type != "access":
            raise CredentialsException()

    except jwt.PyJWTError:
        raise CredentialsException() from None

    user = db.query(User).filter(User.id == str(user_id)).first()
    if user is None:
        raise CredentialsException()

    return user


def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """
    Optional layer: 'is_active' or banned status
    """
    # if not current_user.is_active:
    #     raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def get_current_workspace(
    workspace_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(get_db)]
) -> UUID:
    """
    Validates that the authenticated user belongs to the workspace in the URL path.
    Returns the workspace_id if valid, otherwise aborts with a 403 Forbidden.
    """
    query = select(WorkspaceUser).where(
        WorkspaceUser.user_id == current_user.id,
        WorkspaceUser.workspace_id == workspace_id
    )
    result = db.execute(query)
    association = result.scalar_one_or_none()

    if not association:
        raise WorkspaceNotFound()

    return workspace_id
