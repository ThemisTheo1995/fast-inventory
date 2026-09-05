from datetime import UTC, datetime

from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.erp.api.auth.exceptions import (
    AccountAlreadyOnboardedExceptionError,
    CredentialsExceptionError,
    InvitationNotFoundExceptionError,
    OnboardingFailedExceptionError,
    PricingPlanDoesNotExistError,
    TokenInvalidError,
    UserExistsExceptionError,
)
from src.erp.api.auth.models import User, UserSession
from src.erp.api.auth.schemas.user import (
    LoginResult,
    OnboardResult,
    RegisterRequest,
    RegisterResult,
    UserCreate,
)
from src.erp.api.auth.utils import (
    create_access_token,
    decode_token,
    generate_token_pair,
    get_password_hash,
    verify_password,
)
from src.erp.api.pricing.models import PricingPlan, PricingSubscription
from src.erp.api.workspace.models import Workspace
from src.erp.api.workspace_user.enums import InvitationStatusEnum, WorkspaceRoleEnum
from src.erp.api.workspace_user.models import WorkspaceUser


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def register(self, data: RegisterRequest) -> RegisterResult:
        """Service to register completely new customers."""

        # 1. Pre-checks
        #   Email existence check
        existing_user_result = await self.db.execute(select(User).where(User.email == data.user.email))
        if existing_user_result.scalar_one_or_none():
            raise UserExistsExceptionError()

        #   Price plan existence check
        plan_result = await self.db.execute(select(PricingPlan).where(PricingPlan.name == data.plan))
        selected_plan = plan_result.scalar_one_or_none()

        if not selected_plan:
            raise PricingPlanDoesNotExistError()

        try:
            # 2. Create the Workspace
            workspace = Workspace(name=data.workspace.name, email=data.workspace.email)
            self.db.add(workspace)
            await self.db.flush()

            # 3 Create Subscription
            subscription = PricingSubscription(
                workspace_id=workspace.id, plan_id=selected_plan.id, is_active=True, is_paused=False
            )
            self.db.add(subscription)

            # 4. Create the User
            hashed_pw = get_password_hash(data.user.password)
            user = User(
                email=data.user.email,
                first_name=data.user.first_name,
                last_name=data.user.last_name,
                hashed_password=hashed_pw,
            )
            self.db.add(user)
            await self.db.flush()

            # 5. Link them via WorkspaceUser
            workspace_user = WorkspaceUser(
                user_id=user.id,
                workspace_id=workspace.id,
                role=WorkspaceRoleEnum.FULL_ADMIN,
                status=InvitationStatusEnum.ACTIVE,
            )
            self.db.add(workspace_user)
            await self.db.flush()

            # 6. Generate JWT tokens
            tokens = generate_token_pair(user.id)
            refresh_payload = decode_token(tokens["refresh_token"])

            # 7. Track the session in the DB
            expires_at = datetime.fromtimestamp(refresh_payload["exp"], tz=UTC)
            user_session = UserSession(user_id=user.id, session_id=refresh_payload["jti"], expires_at=expires_at)
            self.db.add(user_session)

            await self.db.commit()

        except Exception as e:
            await self.db.rollback()
            raise OnboardingFailedExceptionError() from e

        else:
            return RegisterResult(
                workspace_id=workspace_user.workspace_id,
                access_token=tokens["access_token"],
                refresh_token=tokens["refresh_token"],
            )

    async def onboard(self, data: UserCreate) -> OnboardResult:
        """Service to fully onboard and activate an invited workspace user."""

        # 1. Locate the pre-seeded user record from invite_member step
        user_result = await self.db.execute(select(User).where(User.email == data.email))
        user = user_result.scalar_one_or_none()

        if not user:
            raise InvitationNotFoundExceptionError()

        # 2. Verify there is a pending workspace link for this user
        ws_user_result = await self.db.execute(
            select(WorkspaceUser).where(WorkspaceUser.is_deleted.is_(False), WorkspaceUser.user_id == user.id)
        )
        workspace_user = ws_user_result.scalar_one_or_none()

        if not workspace_user:
            raise InvitationNotFoundExceptionError()

        if workspace_user.status != InvitationStatusEnum.PENDING.value and user.hashed_password:
            raise AccountAlreadyOnboardedExceptionError()

        try:
            # 3. Finalise User account details
            user.hashed_password = get_password_hash(data.password)
            user.first_name = data.first_name
            user.last_name = data.last_name

            # 4. Promote status to active
            workspace_user.status = InvitationStatusEnum.ACTIVE.value

            # 5. Issue Auth Token Infrastructure payload
            tokens = generate_token_pair(user.id)
            refresh_payload = decode_token(tokens["refresh_token"])

            # 6. Save tracking session
            expires_at = datetime.fromtimestamp(refresh_payload["exp"], tz=UTC)
            user_session = UserSession(user_id=user.id, session_id=refresh_payload["jti"], expires_at=expires_at)
            self.db.add(user_session)

            await self.db.commit()

            # 7. Construct the response schema
            return OnboardResult(
                workspace_id=workspace_user.workspace_id,
                access_token=tokens["access_token"],
                refresh_token=tokens["refresh_token"],
            )

        except Exception as e:
            await self.db.rollback()
            raise OnboardingFailedExceptionError() from e

    async def login(self, data: OAuth2PasswordRequestForm) -> LoginResult:
        """Service to login users via OAuth2 Form Data."""

        # 1. Find user by email (eagerly load workspaces to prevent MissingGreenlet lazy-load crashes)
        user_result = await self.db.execute(
            select(User).options(selectinload(User.workspaces)).where(User.email == data.username)
        )
        user = user_result.scalar_one_or_none()

        # 2. Verify password
        if not user or not verify_password(data.password, user.hashed_password):
            raise CredentialsExceptionError()

        # 3. Generate tokens
        tokens = generate_token_pair(user.id)
        refresh_payload = decode_token(tokens["refresh_token"])

        # 4. Create new UserSession record (Stateful auth)
        await self.db.execute(delete(UserSession).where(UserSession.user_id == user.id))

        # 5. Create new single active UserSession record
        expires_at = datetime.fromtimestamp(refresh_payload["exp"], tz=UTC)
        new_session = UserSession(user_id=user.id, session_id=refresh_payload["jti"], expires_at=expires_at)
        self.db.add(new_session)
        await self.db.commit()

        workspace_user = user.workspaces[0]

        return LoginResult(
            workspace_id=workspace_user.workspace_id,
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
        )

    async def logout(self, refresh_token: str) -> None:
        """Service to logout user."""
        try:
            # 1. Decode the refresh token to extract the user (sub) and session ID (jti)
            payload = decode_token(refresh_token)

            user_id = payload.get("sub")
            session_id = payload.get("jti")

            if not user_id or not session_id:
                return

            # 2. Delete the specific session from the database using SQLAlchemy 2.0 delete()
            result = await self.db.execute(
                delete(UserSession).where(UserSession.user_id == user_id, UserSession.session_id == session_id)
            )

            # 3. Commit the transaction if a session was found and deleted
            if result.rowcount > 0:
                await self.db.commit()

        except Exception:
            await self.db.rollback()

    async def refresh_token(self, refresh_token: str | None) -> str:
        if not refresh_token:
            raise TokenInvalidError()

        payload = decode_token(refresh_token)

        if payload.get("type") != "refresh":
            raise TokenInvalidError()

        user_id = payload.get("sub")
        session_id = payload.get("jti")

        if not user_id or not session_id:
            raise TokenInvalidError()

        session_result = await self.db.execute(
            select(UserSession).where(UserSession.user_id == user_id, UserSession.session_id == session_id)
        )
        active_session = session_result.scalar_one_or_none()

        if not active_session:
            raise TokenInvalidError()

        return create_access_token(subject=user_id)
