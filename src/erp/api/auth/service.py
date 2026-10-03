from datetime import UTC, datetime, timedelta

from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from erp.api.auth.exceptions import (
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
from erp.api.auth.models import User, UserSession
from erp.api.auth.schemas.user import (
    LoginResult,
    OnboardResult,
    RegisterRequest,
    RegisterResult,
    UserCreate,
)
from erp.api.auth.utils import (
    create_access_token,
    decode_password_reset_token,
    decode_token,
    decode_whitelist_user_token,
    generate_password_reset_token,
    generate_token_pair,
    generate_whitelist_token,
    get_password_hash,
    verify_password,
)
from erp.api.pricing.models import PricingPlan, PricingSubscription
from erp.api.workspace.exceptions import WorkspaceAlreadyExistsError
from erp.api.workspace.models import Workspace
from erp.api.workspace_user.enums import InvitationStatusEnum, WorkspaceRoleEnum
from erp.api.workspace_user.models import WorkspaceUser
from erp.services.emails.builder import build_password_reset_email, build_welcome_email
from erp.services.emails.factory import get_email_provider


class AuthService:
    PASSWORD_RESET_COOLDOWN_MINUTES = 5

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def verify(self, token: str) -> None:
        """Verifies the token and flips is_whitelisted to True."""
        user_id = decode_whitelist_user_token(token)

        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise UserNotFoundError()

        if not user.is_whitelisted:
            user.is_whitelisted = True
            await self.db.commit()

    async def register(self, data: RegisterRequest) -> RegisterResult:
        """Registers a new user with is_whitelisted=False and returns activation details."""
        # 1. User check
        existing_user_result = await self.db.execute(select(User).where(User.email == data.user.email))
        if existing_user_result.scalar_one_or_none():
            raise UserExistsExceptionError()

        # 2. Pricing Plan check
        plan_result = await self.db.execute(select(PricingPlan).where(PricingPlan.name == data.plan))
        selected_plan = plan_result.scalar_one_or_none()
        if not selected_plan:
            raise PricingPlanDoesNotExistError()

        # 3. Workspace check
        existing_workspace_result = await self.db.execute(
            select(Workspace).where(Workspace.email == data.workspace.email)
        )
        if existing_workspace_result.scalar_one_or_none():
            raise WorkspaceAlreadyExistsError()

        try:
            # 4. Create Workspace
            workspace = Workspace(name=data.workspace.name, email=data.workspace.email)
            self.db.add(workspace)
            await self.db.flush()

            # 5. Create Subscription
            subscription = PricingSubscription(
                workspace_id=workspace.id,
                plan_id=selected_plan.id,
                is_active=True,
                is_paused=False,
            )
            self.db.add(subscription)

            # 6. Create User
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

            # 7. Link User to Workspace
            workspace_user = WorkspaceUser(
                user_id=user.id,
                workspace_id=workspace.id,
                role=WorkspaceRoleEnum.FULL_ADMIN,
                status=InvitationStatusEnum.ACTIVE,
            )
            self.db.add(workspace_user)

            # 8. Generate JWT tokens
            tokens = generate_token_pair(user.id)
            refresh_payload = decode_token(tokens["refresh_token"])

            # 9. Track session in DB
            expires_at = datetime.fromtimestamp(refresh_payload["exp"], tz=UTC)
            user_session = UserSession(
                user_id=user.id,
                session_id=refresh_payload["jti"],
                expires_at=expires_at,
            )
            self.db.add(user_session)

            await self.db.commit()

        except Exception as e:
            await self.db.rollback()
            raise OnboardingFailedExceptionError() from e

        # --- Side Effects (Post-Commit) ---
        whitelist_token = generate_whitelist_token(user.id)

        verification_message = build_welcome_email(
            recipient=user.email,
            whitelisted_token=whitelist_token,
            user_name=user.first_name or "there",
        )

        email_provider = get_email_provider()
        await email_provider.send_email(verification_message)

        return RegisterResult(
            whitelisted_token=whitelist_token,
            workspace_id=workspace_user.workspace_id,
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            is_whitelisted=user.is_whitelisted,
        )

    async def onboard(self, data: UserCreate) -> OnboardResult:
        """Service to fully onboard and activate an invited workspace user."""

        user_result = await self.db.execute(select(User).where(User.email == data.email))
        user = user_result.scalar_one_or_none()

        if not user:
            raise InvitationNotFoundExceptionError()

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
            user.hashed_password = get_password_hash(data.password)
            user.first_name = data.first_name
            user.last_name = data.last_name

            workspace_user.status = InvitationStatusEnum.ACTIVE

            tokens = generate_token_pair(user.id)
            refresh_payload = decode_token(tokens["refresh_token"])

            expires_at = datetime.fromtimestamp(refresh_payload["exp"], tz=UTC)
            user_session = UserSession(
                user_id=user.id,
                session_id=refresh_payload["jti"],
                expires_at=expires_at,
            )
            self.db.add(user_session)

            await self.db.commit()

        except Exception as e:
            await self.db.rollback()
            raise OnboardingFailedExceptionError() from e

        # --- Side Effects & Output (Post-Commit) ---
        whitelist_token: str | None = None
        if not user.is_whitelisted:
            whitelist_token = generate_whitelist_token(user.id)
            verification_message = build_welcome_email(
                recipient=user.email,
                whitelisted_token=whitelist_token,
                user_name=user.first_name or "there",
            )
            email_provider = get_email_provider()
            await email_provider.send_email(verification_message)

        return OnboardResult(
            is_whitelisted=user.is_whitelisted,
            workspace_id=workspace_user.workspace_id,
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
        )

    async def login(self, data: OAuth2PasswordRequestForm) -> LoginResult:
        """Service to login users via OAuth2 Form Data."""
        user_result = await self.db.execute(
            select(User).options(selectinload(User.workspaces)).where(User.email == data.username)
        )
        user = user_result.scalar_one_or_none()

        if not user or not user.hashed_password or not verify_password(data.password, user.hashed_password):
            raise CredentialsExceptionError()

        if not user.is_whitelisted:
            raise UserNotWhitelistedError()

        if not user.workspaces:
            raise CredentialsExceptionError()
        workspace_user = user.workspaces[0]

        tokens = generate_token_pair(user.id)
        refresh_payload = decode_token(tokens["refresh_token"])

        await self.db.execute(delete(UserSession).where(UserSession.user_id == user.id))

        expires_at = datetime.fromtimestamp(refresh_payload["exp"], tz=UTC)
        new_session = UserSession(user_id=user.id, session_id=refresh_payload["jti"], expires_at=expires_at)
        self.db.add(new_session)
        await self.db.commit()

        return LoginResult(
            workspace_id=workspace_user.workspace_id,
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            is_whitelisted=user.is_whitelisted,
        )

    async def logout(self, refresh_token: str, revoke_all: bool = True) -> None:
        """Service to logout user. Option to revoke current session or all active sessions."""
        try:
            payload = decode_token(refresh_token)
            user_id = payload.get("sub")
            session_id = payload.get("jti")

            if not user_id:
                return

            if revoke_all or not session_id:
                stmt = delete(UserSession).where(UserSession.user_id == user_id)
            else:
                stmt = delete(UserSession).where(
                    UserSession.user_id == user_id,
                    UserSession.session_id == session_id,
                )

            result = await self.db.execute(stmt)
            if result.rowcount > 0:
                await self.db.commit()

        except Exception:
            await self.db.rollback()

    async def refresh_token(self, refresh_token: str | None) -> str:
        """Refreshes access token if the refresh token is valid and session exists."""
        if not refresh_token:
            raise TokenInvalidError()

        try:
            payload = decode_token(refresh_token)
        except Exception as e:
            raise TokenInvalidError() from e

        if payload.get("type") != "refresh":
            raise TokenInvalidError()

        user_id = payload.get("sub")
        session_id = payload.get("jti")

        if not user_id or not session_id:
            raise TokenInvalidError()

        session_result = await self.db.execute(
            select(UserSession).where(
                UserSession.user_id == user_id,
                UserSession.session_id == session_id,
            )
        )
        active_session = session_result.scalar_one_or_none()

        if not active_session:
            raise TokenInvalidError()

        if active_session.expires_at and active_session.expires_at < datetime.now(UTC):
            await self.db.delete(active_session)
            await self.db.commit()
            raise TokenInvalidError()

        return create_access_token(subject=user_id)

    async def request_password_reset(self, email: str) -> None:
        """
        Initiates password reset by generating a token and dispatching an email.
        Includes guards for anti-enumeration and email rate-limiting.
        """
        now = datetime.now(UTC)

        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        # Anti-enumeration guard: Exit silently if user doesn't exist
        if not user:
            return

        # Rate-limiting guard: Exit silently if within cooldown window
        if user.last_password_reset_sent_at:
            cooldown = user.last_password_reset_sent_at + timedelta(minutes=self.PASSWORD_RESET_COOLDOWN_MINUTES)
            if now < cooldown:
                return

        # 3. Update timestamp and persist
        user.last_password_reset_sent_at = now
        await self.db.commit()

        # 4. Generate token and send email
        reset_token = generate_password_reset_token(user.id)

        reset_message = build_password_reset_email(
            recipient=user.email,
            reset_token=reset_token,
            user_name=user.first_name or "there",
        )

        email_provider = get_email_provider()
        await email_provider.send_email(reset_message)

    async def confirm_password_reset(self, token: str, new_password: str) -> None:
        """
        Verifies reset token, updates hashed password, and revokes all active user sessions.
        """
        user_id = decode_password_reset_token(token)

        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise UserNotFoundError()

        # Update password
        user.hashed_password = get_password_hash(new_password)

        # Revoke all active sessions across devices
        await self.db.execute(delete(UserSession).where(UserSession.user_id == user.id))

        await self.db.commit()
