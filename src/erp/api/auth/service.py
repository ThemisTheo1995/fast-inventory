from datetime import UTC, datetime

from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from erp.api.auth.exceptions import (
    CredentialsException,
    OnboardingFailedException,
    TokenInvalidError,
    UserExistsException,
)
from erp.api.auth.models import User, UserSession
from erp.api.auth.schemas import LogoutRequest, RegisterRequest, TokenRefreshResponse, TokenResponse
from erp.api.auth.utils import (
    create_access_token,
    decode_token,
    generate_token_pair,
    get_password_hash,
    verify_password,
)
from erp.api.workspace.enums import InvitationStatusEnum, WorkspaceRoleEnum
from erp.api.workspace.models import Workspace, WorkspaceUser


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def onboard(self, data: RegisterRequest) -> WorkspaceUser:
        """Service to onbaord completely new customers."""

        # 1. Pre-check email existence
        if self.db.query(User).filter(User.email == data.user.email).first():
            raise UserExistsException()

        try:
            # 2. Create the Workspace
            workspace = Workspace(name=data.workspace.name, email=data.workspace.email)
            self.db.add(workspace)
            self.db.flush()

            # 3. Create the User
            hashed_pw = get_password_hash(data.user.password)
            user = User(
                email=data.user.email,
                first_name=data.user.first_name,
                last_name=data.user.last_name,
                hashed_password=hashed_pw
            )
            self.db.add(user)
            self.db.flush()

            # 4. Link them via WorkspaceUser
            workspace_user = WorkspaceUser(
                user_id=user.id,
                workspace_id=workspace.id,
                role=WorkspaceRoleEnum.FULL_ADMIN,
                status=InvitationStatusEnum.ACTIVE
            )
            self.db.add(workspace_user)
            self.db.flush()

            # 5. Generate JWT tokens
            tokens = generate_token_pair(user.id)
            refresh_payload = decode_token(tokens["refresh_token"])

            # 6. Track the session in the DB
            expires_at = datetime.fromtimestamp(refresh_payload["exp"], tz=UTC)
            user_session = UserSession(
                user_id=user.id,
                session_id=refresh_payload["jti"],
                expires_at=expires_at
            )
            self.db.add(user_session)

            self.db.commit()
            return workspace_user

        except Exception as e:
            self.db.rollback()
            raise OnboardingFailedException(e) from e

    def login(self, data: OAuth2PasswordRequestForm) -> TokenResponse:
        """Service to login users via OAuth2 Form Data."""

        # 1. Find user by email
        user = self.db.query(User).filter(User.email == data.username).first()

        # 2. Verify password
        if not user or not verify_password(data.password, user.hashed_password):
            raise CredentialsException()

        # 3. Generate tokens
        tokens = generate_token_pair(user.id)
        refresh_payload = decode_token(tokens["refresh_token"])

        # 4. Create new UserSession record (Stateful auth)
        self.db.query(UserSession).filter(UserSession.user_id == user.id).delete(synchronize_session=False)

        # 5. Create new single active UserSession record
        expires_at = datetime.fromtimestamp(refresh_payload["exp"], tz=UTC)
        new_session = UserSession(
            user_id=user.id,
            session_id=refresh_payload["jti"],
            expires_at=expires_at
        )
        self.db.add(new_session)
        self.db.commit()

        workspace_link = user.workspaces[0]

        return TokenResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            # Ensure this is exactly "bearer" (lowercase is standard, but Swagger handles both)
            token_type="bearer", 
            workspace_id=workspace_link.workspace_id
        )

    def logout(self, data: LogoutRequest) -> None:
        """Service to logout user."""
        try:
            # 1. Decode the refresh token to extract the user (sub) and session ID (jti)
            payload = decode_token(data.refresh_token)

            user_id = payload.get("sub")
            session_id = payload.get("jti")

            if not user_id or not session_id:
                return

            # 2. Delete the specific session from the database
            deleted_count = self.db.query(UserSession).filter(
                UserSession.user_id == user_id,
                UserSession.session_id == session_id
            ).delete(synchronize_session=False)

            # 3. Commit the transaction if a session was found and deleted
            if deleted_count > 0:
                self.db.commit()

        except Exception:
            self.db.rollback()
            pass

    def refresh_token(self, refresh_token: str) -> TokenRefreshResponse:
        """
        Validates a refresh token against the database session store
        and issues a new short-lived access token.
        """
        payload = decode_token(refresh_token)

        if payload.get("type") != "refresh":
            raise TokenInvalidError()

        user_id = payload.get("sub")
        session_id = payload.get("jti")

        if not user_id or not session_id:
            raise TokenInvalidError()

        active_session = self.db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.session_id == session_id
        ).first()

        if not active_session:
            # The session was revoked or overwritten by a newer login
            raise TokenInvalidError()

        # 3. Generate a new short-lived access token
        new_access_token = create_access_token(subject=user_id)

        # You can choose to return just the new access token,
        # or pass back the same refresh token to keep the payload consistent.
        return TokenRefreshResponse(
            access_token=new_access_token,
            refresh_token=refresh_token,
            token_type="bearer"
        )
