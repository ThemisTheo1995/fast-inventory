from datetime import UTC, datetime

from fastapi import BackgroundTasks
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
    UserNotFoundError,
    UserNotWhitelistedError,
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
    decode_whitelist_user_token,
    generate_token_pair,
    generate_whitelist_token,
    get_password_hash,
    verify_password,
)
from src.erp.api.pricing.models import PricingPlan, PricingSubscription
from src.erp.api.workspace.exceptions import WorkspaceAlreadyExistsError
from src.erp.api.workspace.models import Workspace
from src.erp.api.workspace_user.enums import InvitationStatusEnum, WorkspaceRoleEnum
from src.erp.api.workspace_user.models import WorkspaceUser
from src.erp.services.emails.builder import build_welcome_email
from src.erp.services.emails.factory import get_email_provider


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def verify(self, token: str) -> None:
        """Verifies the token and flips is_whitelisted to True."""

        user_id = decode_whitelist_user_token(token)

        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise UserNotFoundError()

        if user.is_whitelisted:
            return

        user.is_whitelisted = True
        await self.db.commit()

    async def register(self, data: RegisterRequest, background_tasks: BackgroundTasks | None = None) -> RegisterResult:
        """Registers a new user with is_whitelisted=False and returns activation details."""
        whitelist_token: str | None = None

        # User check
        existing_user_result = await self.db.execute(select(User).where(User.email == data.user.email))
        if existing_user_result.scalar_one_or_none():
            raise UserExistsExceptionError()

        # Pricing Plan check
        plan_result = await self.db.execute(select(PricingPlan).where(PricingPlan.name == data.plan))
        selected_plan = plan_result.scalar_one_or_none()
        if not selected_plan:
            raise PricingPlanDoesNotExistError()

        # Workspace check
        existing_workspace_result = await self.db.execute(
            select(Workspace).where(Workspace.email == data.workspace.email)
        )
        if existing_workspace_result.scalar_one_or_none():
            raise WorkspaceAlreadyExistsError()
        try:
            # 1. Create Workspace
            workspace = Workspace(name=data.workspace.name, email=data.workspace.email)
            self.db.add(workspace)
            await self.db.flush()

            # 2. Create Subscription
            subscription = PricingSubscription(
                workspace_id=workspace.id, plan_id=selected_plan.id, is_active=True, is_paused=False
            )
            self.db.add(subscription)

            # 3. Create blacklisted User
            hashed_pw = get_password_hash(data.user.password)
            user = User(
                email=data.user.email,
                first_name=data.user.first_name,
                last_name=data.user.last_name,
                hashed_password=hashed_pw,
                is_whitelisted=False,
            )
            self.db.add(user)
            await self.db.flush()

            # 4. Link User to Workspace
            workspace_user = WorkspaceUser(
                user_id=user.id,
                workspace_id=workspace.id,
                role=WorkspaceRoleEnum.FULL_ADMIN,
                status=InvitationStatusEnum.ACTIVE,
            )
            self.db.add(workspace_user)
            await self.db.flush()

            # 5. Generate JWT tokens
            tokens = generate_token_pair(user.id)
            refresh_payload = decode_token(tokens["refresh_token"])

            # 6. Track the session in the DB
            expires_at = datetime.fromtimestamp(refresh_payload["exp"], tz=UTC)
            user_session = UserSession(user_id=user.id, session_id=refresh_payload["jti"], expires_at=expires_at)
            self.db.add(user_session)

            await self.db.commit()

        except Exception as e:
            await self.db.rollback()
            raise OnboardingFailedExceptionError() from e

        # --- Side Effects (Post-Commit) ---

        if background_tasks:
            # 7. Generate Whitelist Token
            whitelist_token = generate_whitelist_token(user.id)

            # 8. Build message
            verification_message = build_welcome_email(
                recipient=user.email,
                whitelisted_token=whitelist_token,
                user_name=user.first_name or "there",
            )

            # 9. Queue email task
            email_provider = get_email_provider()
            background_tasks.add_task(email_provider.send_email, verification_message)

        return RegisterResult(
            whitelisted_token=whitelist_token,
            workspace_id=workspace_user.workspace_id,
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            is_whitelisted=user.is_whitelisted,
        )

    async def onboard(self, data: UserCreate, background_tasks: BackgroundTasks | None = None) -> OnboardResult:
        """Service to fully onboard and activate an invited workspace user."""

        whitelist_token: str | None = None

        # 1. Locate the pre-seeded user record from invite_member step
        user_result = await self.db.execute(select(User).where(User.email == data.email))
        user = user_result.scalar_one_or_none()

        if not user:
            raise InvitationNotFoundExceptionError()

        # 2. Locate the pending workspace invitation for this user
        ws_user_result = await self.db.execute(
            select(WorkspaceUser).where(
                WorkspaceUser.is_deleted.is_(False),
                WorkspaceUser.user_id == user.id,
                WorkspaceUser.status == InvitationStatusEnum.PENDING,
            )
        )
        workspace_user = ws_user_result.scalar_one_or_none()

        if not workspace_user:
            if user.hashed_password:
                raise AccountAlreadyOnboardedExceptionError()
            raise InvitationNotFoundExceptionError()

        try:
            # 3. Finalise User account details
            user.hashed_password = get_password_hash(data.password)
            user.first_name = data.first_name
            user.last_name = data.last_name

            # 4. Promote status to active
            workspace_user.status = InvitationStatusEnum.ACTIVE

            # 5. Issue Auth Token Infrastructure payload
            tokens = generate_token_pair(user.id)
            refresh_payload = decode_token(tokens["refresh_token"])

            # 6. Save tracking session
            expires_at = datetime.fromtimestamp(refresh_payload["exp"], tz=UTC)
            user_session = UserSession(user_id=user.id, session_id=refresh_payload["jti"], expires_at=expires_at)
            self.db.add(user_session)

            # Commit database transaction
            await self.db.commit()

        except Exception as e:
            await self.db.rollback()
            raise OnboardingFailedExceptionError() from e

        # --- Side Effects & Output (Post-Commit) ---

        # 7. Construct and send verification email if user is not whitelisted
        if not user.is_whitelisted and background_tasks:
            whitelist_token = generate_whitelist_token(user.id)
            verification_message = build_welcome_email(
                recipient=user.email,
                whitelisted_token=whitelist_token,
                user_name=user.first_name or "there",
            )
            email_provider = get_email_provider()
            background_tasks.add_task(email_provider.send_email, verification_message)

        # 8. Construct response schema
        return OnboardResult(
            is_whitelisted=user.is_whitelisted,
            workspace_id=workspace_user.workspace_id,
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
        )

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

        # 3. Is Whitelisted
        if not user.is_whitelisted:
            raise UserNotWhitelistedError()

        # 4. Generate tokens
        tokens = generate_token_pair(user.id)
        refresh_payload = decode_token(tokens["refresh_token"])

        # 5. Create new UserSession record (Stateful auth)
        await self.db.execute(delete(UserSession).where(UserSession.user_id == user.id))

        # 6. Create new single active UserSession record
        expires_at = datetime.fromtimestamp(refresh_payload["exp"], tz=UTC)
        new_session = UserSession(user_id=user.id, session_id=refresh_payload["jti"], expires_at=expires_at)
        self.db.add(new_session)
        await self.db.commit()

        workspace_user = user.workspaces[0]

        return LoginResult(
            workspace_id=workspace_user.workspace_id,
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            is_whitelisted=user.is_whitelisted,
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
