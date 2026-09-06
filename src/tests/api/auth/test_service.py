from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.api.auth.exceptions import (
    AccountAlreadyOnboardedExceptionError,
    CredentialsExceptionError,
    InvitationNotFoundExceptionError,
    OnboardingFailedExceptionError,
    PricingPlanDoesNotExistError,
    TokenInvalidError,
    UserExistsExceptionError,
)
from erp.api.auth.models import User, UserSession
from erp.api.auth.schemas.user import RegisterRequest, UserCreate
from erp.api.auth.service import AuthService
from erp.api.auth.utils import create_access_token, decode_token, generate_token_pair, get_password_hash
from erp.api.pricing.enums import PlanName
from erp.api.pricing.models import PricingPlan
from erp.api.workspace.models import Workspace
from erp.api.workspace.schemas import WorkspaceCreate
from erp.api.workspace_user.enums import InvitationStatusEnum, WorkspaceRoleEnum
from erp.api.workspace_user.models import WorkspaceUser

# ============================================================================
# REGISTER SERVICE TESTS (`register`)
# ============================================================================


async def test_register_happy_path(db_session: AsyncSession):
    """
    Valid complete request should step cleanly through creating a Workspace,
    User, binding WorkspaceUser link, generating tokens, tracking session state,
    and cleanly committing the whole atomic unit.
    """
    auth_service = AuthService(db_session)
    request_data = RegisterRequest(
        user=UserCreate(email="happy@example.com", password="SecurePassword123!", first_name="John", last_name="Doe"),
        workspace=WorkspaceCreate(name="Happy Tech LLC", email="billing@happytech.com"),
        plan=next(iter(PlanName)),
    )

    await auth_service.register(request_data)

    res_ws_user = await db_session.execute(select(WorkspaceUser).join(User).where(User.email == "happy@example.com"))
    workspace_user = res_ws_user.scalar_one_or_none()

    # Check returned DTO
    assert workspace_user is not None
    assert workspace_user.role == WorkspaceRoleEnum.FULL_ADMIN
    assert workspace_user.status == InvitationStatusEnum.ACTIVE

    # Check Database Mutations
    res_user = await db_session.execute(select(User).where(User.email == "happy@example.com"))
    user = res_user.scalar_one_or_none()
    assert user is not None
    assert user.first_name == "John"

    res_ws = await db_session.execute(select(Workspace).where(Workspace.name == "Happy Tech LLC"))
    workspace = res_ws.scalar_one_or_none()
    assert workspace is not None
    assert workspace.email == "billing@happytech.com"

    res_session = await db_session.execute(select(UserSession).where(UserSession.user_id == user.id))
    session = res_session.scalar_one_or_none()
    assert session is not None
    assert session.expires_at > datetime.now(UTC)


async def test_register_exception_user_already_exists(db_session: AsyncSession, pricing_plan: PricingPlan):
    """
    If a user email already exists in the system, pre-check must raise
    UserExistsExceptionError immediately before running any downstream database flushes.
    """
    auth_service = AuthService(db_session)

    # Setup pre-existing state
    existing_user = User(email="exists@example.com", first_name="Im", last_name="Here", hashed_password="hashed")
    db_session.add(existing_user)
    await db_session.commit()

    request_data = RegisterRequest(
        user=UserCreate(email="exists@example.com", password="password123"),
        workspace=WorkspaceCreate(name="Ghost Corp", email="ghost@corp.com"),
        plan=pricing_plan.name,
    )

    with pytest.raises(UserExistsExceptionError):
        await auth_service.register(request_data)


async def test_register_exception_database_failure_triggers_rollback(db_session: AsyncSession):
    """
    EXCEPTION PATH & EDGE CASE:
    If any uncaught database/internal error occurs mid-transaction (e.g. JWT token generation failure),
    the system must catch it, execute a transaction rollback to prevent orphaned records,
    and raise an OnboardingFailedExceptionError wrapper.
    """
    auth_service = AuthService(db_session)
    request_data = RegisterRequest(
        user=UserCreate(email="rollback@example.com", password="password123"),
        workspace=WorkspaceCreate(name="Rollback Inc", email="rb@inc.com"),
        plan=next(iter(PlanName)),
    )

    # Force an internal failure mid-flight by patching 'generate_token_pair' to raise a runtime error
    with (
        patch(
            "erp.api.auth.service.generate_token_pair",
            side_effect=ValueError("JWT Crypto System Error"),
        ),
        pytest.raises(OnboardingFailedExceptionError),
    ):
        await auth_service.register(request_data)

    # Assert that rollback successfully kept database clean of partial/orphaned items
    db_session.expire_all()

    res_user = await db_session.execute(select(User).where(User.email == "rollback@example.com"))
    assert res_user.scalar_one_or_none() is None

    res_ws = await db_session.execute(select(Workspace).where(Workspace.name == "Rollback Inc"))
    assert res_ws.scalar_one_or_none() is None


async def test_register_exception_pricing_plan_does_not_exist(db_session: AsyncSession):
    """
    Verifies that registering with an unknown or unavailable pricing plan
    immediately halts the process and raises PricingPlanDoesNotExistError.
    """
    await db_session.execute(delete(PricingPlan))
    await db_session.commit()

    auth_service = AuthService(db_session)

    request_data = RegisterRequest(
        user=UserCreate(email="noplan@example.com", password="SecurePassword123!"),
        workspace=WorkspaceCreate(name="No Plan LLC", email="noplan@corp.com"),
        plan=PlanName.PRO,
    )

    with pytest.raises(PricingPlanDoesNotExistError):
        await auth_service.register(request_data)


#  ============================================================================
#  LOGIN SERVICE TESTS (`login`)
#  ============================================================================


async def test_login_happy_path(db_session: AsyncSession):
    """
    Providing matching credentials must successfully yield a LoginResponse,
    clear out previous session records for security, and spin up a single new tracking session.
    """
    auth_service = AuthService(db_session)
    raw_password = "MySuperSecretPassword"

    # Set up user and link workspace
    user = User(
        email="login_ok@example.com",
        first_name="Login",
        last_name="User",
        hashed_password=get_password_hash(raw_password),
    )
    workspace = Workspace(name="User Space", email="space@user.com")
    db_session.add_all([user, workspace])
    await db_session.flush()

    link = WorkspaceUser(
        user_id=user.id,
        workspace_id=workspace.id,
        role=WorkspaceRoleEnum.FULL_ADMIN,
        status=InvitationStatusEnum.ACTIVE,
    )
    db_session.add(link)
    await db_session.commit()

    login_data = OAuth2PasswordRequestForm(username="login_ok@example.com", password=raw_password)

    response = await auth_service.login(login_data)

    assert response.access_token is not None
    assert response.refresh_token is not None
    assert response.workspace_id == workspace.id

    # Assert stateful active session exists
    res_session = await db_session.execute(select(UserSession).where(UserSession.user_id == user.id))
    session = res_session.scalar_one_or_none()
    assert session is not None


async def test_login_user_with_no_workspaces_raises_index_error(db_session: AsyncSession):
    """
    If a user somehow exists in the database without a mandatory bound workspace,
    attempting to log them in must immediately raise an IndexError.
    """
    auth_service = AuthService(db_session)
    raw_password = "corrupted_state_password"
    user = User(
        email="orphan@example.com",
        first_name="Orphaned",
        last_name="User",
        hashed_password=get_password_hash(raw_password),
    )
    db_session.add(user)
    await db_session.flush()

    login_data = OAuth2PasswordRequestForm(username="orphan@example.com", password=raw_password)

    with pytest.raises(IndexError):
        await auth_service.login(login_data)


@pytest.mark.parametrize(
    "email, password",
    [
        ("exists_user@example.com", "incorrect_password"),
        ("missing_user@example.com", "any_password"),
        ("exists_user@example.com", ""),
    ],
)
async def test_login_exception_invalid_credentials(db_session: AsyncSession, email, password):
    """
    Any invalid permutation of username or password must safely bubble up a unified
    CredentialsExceptionError to obscure system internals and block automated user enumeration.
    """
    auth_service = AuthService(db_session)

    user = User(
        email="exists_user@example.com",
        first_name="Target",
        last_name="User",
        hashed_password=get_password_hash("real_password"),
    )
    workspace = Workspace(name="Target Space", email="target@space.com")
    db_session.add_all([user, workspace])
    await db_session.flush()

    link = WorkspaceUser(
        user_id=user.id,
        workspace_id=workspace.id,
        role=WorkspaceRoleEnum.FULL_ADMIN,
        status=InvitationStatusEnum.ACTIVE,
    )
    db_session.add(link)
    await db_session.flush()

    login_data = OAuth2PasswordRequestForm(username=email, password=password)

    with pytest.raises(CredentialsExceptionError):
        await auth_service.login(login_data)


async def test_login_purges_multiple_concurrent_sessions(db_session: AsyncSession):
    """
    If a user has somehow accumulated multiple tracking sessions in the database,
    logging in must safely purge ALL old sessions to preserve strict single-active-session bounds.
    """
    auth_service = AuthService(db_session)
    raw_pw = "pass123"
    user = User(email="purge@example.com", first_name="P", last_name="U", hashed_password=get_password_hash(raw_pw))
    workspace = Workspace(name="Purge Corp", email="purge@corp.com")
    db_session.add_all([user, workspace])
    await db_session.flush()

    link = WorkspaceUser(
        user_id=user.id,
        workspace_id=workspace.id,
        role=WorkspaceRoleEnum.FULL_ADMIN,
        status=InvitationStatusEnum.ACTIVE,
    )

    session_1 = UserSession(user_id=user.id, session_id="session-alpha", expires_at=datetime.now(UTC))
    session_2 = UserSession(user_id=user.id, session_id="session-beta", expires_at=datetime.now(UTC))

    db_session.add_all([link, session_1, session_2])
    await db_session.flush()

    login_data = OAuth2PasswordRequestForm(username="purge@example.com", password=raw_pw)

    response = await auth_service.login(login_data)
    assert response.workspace_id == workspace.id

    res_sessions = await db_session.execute(select(UserSession).where(UserSession.user_id == user.id))
    remaining_sessions = res_sessions.scalars().all()
    assert len(remaining_sessions) == 1
    assert remaining_sessions[0].session_id not in ["session-alpha", "session-beta"]


# ============================================================================
# LOGOUT SERVICE TESTS (`logout`)
# ============================================================================


async def test_logout_happy_path(db_session: AsyncSession):
    """
    HAPPY PATH:
    Passing a clean active refresh token must successfully remove the specific matching
    session token mapping from the backend persistence layer.
    """
    auth_service = AuthService(db_session)

    user = User(
        email="logout_target@example.com",
        first_name="L",
        last_name="O",
        hashed_password="hash",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    tokens = generate_token_pair(user.id)
    payload = decode_token(tokens["refresh_token"])

    session = UserSession(
        user_id=user.id,
        session_id=payload["jti"],
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db_session.add(session)
    await db_session.commit()

    await auth_service.logout(tokens["refresh_token"])

    db_session.expire_all()

    res_session = await db_session.execute(select(UserSession).where(UserSession.session_id == payload["jti"]))
    assert res_session.scalar_one_or_none() is None


async def test_logout_edge_case_token_missing_claims(db_session: AsyncSession):
    """
    EDGE CASE:
    If a token payload is missing required identity claims, logout must safely return
    without attempting to delete any session.
    """
    auth_service = AuthService(db_session)

    with patch(
        "erp.api.auth.service.decode_token",
        return_value={"type": "refresh"},
    ):
        # Should not raise
        await auth_service.logout("invalid-token-missing-claims")


async def test_logout_silently_swallows_decoding_exceptions(db_session: AsyncSession):
    """
    EXCEPTION PATH:
    If token decoding fails because the token is expired, forged, or malformed,
    logout must swallow the exception and return without leaking errors.
    """
    auth_service = AuthService(db_session)

    with patch(
        "erp.api.auth.service.decode_token",
        side_effect=Exception("Invalid token"),
    ):
        try:
            await auth_service.logout("complete-garbage-token-string")
        except Exception as e:
            pytest.fail(f"Logout service leaked an exception path! Error: {e}")


# ============================================================================
# REFRESH TOKEN SERVICE TESTS (`refresh_token`)
# ============================================================================


async def test_refresh_token_happy_path(db_session: AsyncSession):
    """
    A valid, live refresh token matched against an open tracking record
    must mint a new access token.
    """
    auth_service = AuthService(db_session)

    user = User(
        email="refresh_me@example.com",
        first_name="R",
        last_name="M",
        hashed_password="hash",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    tokens = generate_token_pair(user.id)
    payload = decode_token(tokens["refresh_token"])

    session = UserSession(
        user_id=user.id,
        session_id=payload["jti"],
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db_session.add(session)
    await db_session.commit()

    new_access_token = await auth_service.refresh_token(tokens["refresh_token"])

    assert new_access_token is not None


async def test_refresh_token_exception_wrong_token_type(db_session: AsyncSession):
    """
    If a client attempts to pass a short-lived 'access' token instead of a long-lived 'refresh'
    token into the validation pipeline, it must instantly raise a TokenInvalidError.
    """
    auth_service = AuthService(db_session)

    access_token = create_access_token(subject="user_123")

    with pytest.raises(TokenInvalidError):
        await auth_service.refresh_token(access_token)


@pytest.mark.parametrize(
    "mock_payload",
    [
        {"type": "refresh", "jti": "missing-sub"},  # Missing subject field
        {"type": "refresh", "sub": "missing-jti"},  # Missing tracking ID field
        {"type": "refresh"},  # Missing both fields
    ],
)
async def test_refresh_token_exception_missing_required_claims(db_session: AsyncSession, mock_payload):
    """
    If a valid token payload fails basic validation checks because identity keys
    are missing from the payload dictionary structure, it must raise a TokenInvalidError.
    """
    auth_service = AuthService(db_session)

    with (
        patch("erp.api.auth.service.decode_token", return_value=mock_payload),
        pytest.raises(TokenInvalidError),
    ):
        await auth_service.refresh_token("valid.token.payload")


async def test_refresh_token_exception_session_revoked_or_overwritten(db_session: AsyncSession):
    """
    If a token is cryptographically authentic but its underlying tracking record has been deleted
    from the database, the token exchange must fail.
    """
    auth_service = AuthService(db_session)

    user = User(
        email="stale_session@example.com",
        first_name="S",
        last_name="S",
        hashed_password="hash",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    tokens = generate_token_pair(user.id)

    with pytest.raises(TokenInvalidError):
        await auth_service.refresh_token(tokens["refresh_token"])


# ============================================================================
# ONBOARD SERVICE TESTS (`onboard`)
# ============================================================================


async def test_onboard_happy_path(db_session: AsyncSession):
    """
    Verifies that a successfully invited user (PENDING status, no password)
    can complete onboarding, set their details, and receive valid auth tokens.
    """
    auth_service = AuthService(db_session)

    # 1. Seed a pending invited user
    user = User(email="invitee@test.com", first_name=None, last_name=None, hashed_password=None)
    workspace = Workspace(name="Invite Workspace", email="ws@test.com")
    db_session.add_all([user, workspace])
    await db_session.flush()

    link = WorkspaceUser(
        user_id=user.id,
        workspace_id=workspace.id,
        role=WorkspaceRoleEnum.EDIT_ONLY,
        status=InvitationStatusEnum.PENDING.value,
        is_deleted=False,
    )
    db_session.add(link)
    await db_session.commit()

    # 2. Execute Onboard
    data = UserCreate(email="invitee@test.com", password="NewPassword123", first_name="Jane", last_name="Doe")
    result = await auth_service.onboard(data)

    # 3. Assertions
    assert result.access_token is not None
    assert result.workspace_id == workspace.id

    await db_session.refresh(user)
    await db_session.refresh(link)

    assert user.first_name == "Jane"
    assert user.hashed_password is not None
    assert link.status == InvitationStatusEnum.ACTIVE.value


async def test_onboard_exception_user_not_found(db_session: AsyncSession):
    """
    If the email provided during onboarding doesn't match any pre-seeded user,
    it must raise an InvitationNotFoundExceptionError.
    """
    auth_service = AuthService(db_session)
    data = UserCreate(email="ghost@test.com", password="pw", first_name="Ghost", last_name="User")

    with pytest.raises(InvitationNotFoundExceptionError):
        await auth_service.onboard(data)


async def test_onboard_exception_workspace_link_not_found(db_session: AsyncSession):
    """
    If the user exists but has no active/pending WorkspaceUser link
    (or it was deleted), it must raise an InvitationNotFoundExceptionError.
    """
    auth_service = AuthService(db_session)
    user = User(email="nolink@test.com", first_name=None)
    db_session.add(user)
    await db_session.commit()

    data = UserCreate(email="nolink@test.com", password="pw", first_name="No", last_name="Link")

    with pytest.raises(InvitationNotFoundExceptionError):
        await auth_service.onboard(data)


async def test_onboard_exception_already_onboarded(db_session: AsyncSession):
    """
    If a user is already ACTIVE and already has a password set,
    attempting to onboard again must raise AccountAlreadyOnboardedExceptionError.
    """
    auth_service = AuthService(db_session)

    user = User(email="active@test.com", hashed_password="existing_hash")
    workspace = Workspace(name="Active WS", email="activews@test.com")
    db_session.add_all([user, workspace])
    await db_session.flush()

    link = WorkspaceUser(
        user_id=user.id,
        workspace_id=workspace.id,
        status=InvitationStatusEnum.ACTIVE.value,
        is_deleted=False,
    )
    db_session.add(link)
    await db_session.commit()

    data = UserCreate(email="active@test.com", password="pw", first_name="A", last_name="B")

    with pytest.raises(AccountAlreadyOnboardedExceptionError):
        await auth_service.onboard(data)


async def test_onboard_exception_database_failure_triggers_rollback(db_session: AsyncSession):
    """
    If token generation or any other internal process fails during onboarding,
    it must rollback the transaction so the user remains PENDING.
    """
    auth_service = AuthService(db_session)

    user = User(email="fail@test.com", first_name=None, hashed_password=None)
    workspace = Workspace(name="Fail WS", email="faledws@test.com")
    db_session.add_all([user, workspace])
    await db_session.flush()

    link = WorkspaceUser(
        user_id=user.id,
        workspace_id=workspace.id,
        status=InvitationStatusEnum.PENDING.value,
        is_deleted=False,
    )
    db_session.add(link)
    await db_session.commit()

    data = UserCreate(email="fail@test.com", password="pw", first_name="Should", last_name="Fail")

    with (
        patch(
            "erp.api.auth.service.generate_token_pair",
            side_effect=Exception("Crypto Error"),
        ),
        pytest.raises(OnboardingFailedExceptionError),
    ):
        await auth_service.onboard(data)

    # Verify Rollback
    db_session.expire_all()
    await db_session.refresh(user)
    await db_session.refresh(link)

    assert user.first_name is None
    assert user.hashed_password is None
    assert link.status == InvitationStatusEnum.PENDING.value
