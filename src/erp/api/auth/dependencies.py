from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from erp.api.auth.exceptions import CredentialsExceptionError
from erp.api.auth.models import User
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
            raise CredentialsExceptionError()

    except jwt.PyJWTError:
        raise CredentialsExceptionError() from None

    user = db.query(User).filter(User.id == str(user_id)).first()
    if user is None:
        raise CredentialsExceptionError()

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
