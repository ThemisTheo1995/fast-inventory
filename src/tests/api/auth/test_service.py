from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.security import OAuth2PasswordRequestForm

from src.erp.api.auth.exceptions import (
    CredentialsExceptionError,
    OnboardingFailedExceptionError,
    TokenInvalidError,
    UserExistsExceptionError,
)
from src.erp.api.auth.models import User, UserSession
from src.erp.api.auth.schemas.user import RegisterRequest, UserCreate
from src.erp.api.auth.service import AuthService
from src.erp.api.auth.utils import create_access_token, decode_token, generate_token_pair, get_password_hash
from src.erp.api.pricing.enums import PlanName
from src.erp.api.workspace.models import Workspace
from src.erp.api.workspace.schemas import WorkspaceCreate
from src.erp.api.workspace_user.enums import InvitationStatusEnum, WorkspaceRoleEnum
from src.erp.api.workspace_user.models import WorkspaceUser

# ============================================================================
# REGISTER SERVICE TESTS (`register`)
# ============================================================================


def test_onboard_happy_path(db_session):
    """
    Valid complete request should step cleanly through creating a Workspace,
    User, binding WorkspaceUser link, generating tokens, tracking session state,
    and cleanly committing the whole atomic unit.
    """
    auth_service = AuthService(db_session)
    request_data = RegisterRequest(
        user=UserCreate(email="happy@example.com", password="SecurePassword123!", first_name="John", last_name="Doe"),
        workspace=WorkspaceCreate(name="Happy Tech LLC", email="billing@happytech.com"),
        plan=PlanName.PRO,
    )

    auth_service.register(request_data)

    workspace_user = db_session.query(WorkspaceUser).join(User).filter(User.email == "happy@example.com").first()

    # Check returned DTO
    assert workspace_user.role == WorkspaceRoleEnum.FULL_ADMIN
    assert workspace_user.status == InvitationStatusEnum.ACTIVE

    # Check Database Mutations
    user = db_session.query(User).filter_by(email="happy@example.com").first()
    assert user is not None
    assert user.first_name == "John"

    workspace = db_session.query(Workspace).filter_by(name="Happy Tech LLC").first()
    assert workspace is not None
    assert workspace.email == "billing@happytech.com"

    session = db_session.query(UserSession).filter_by(user_id=user.id).first()
    assert session is not None
    assert session.expires_at > datetime.now(UTC)


def test_onboard_exception_user_already_exists(db_session):
    """
    If a user email already exists in the system, pre-check must raise
    UserExistsExceptionError immediately before running any downstream database flushes.
    """
    auth_service = AuthService(db_session)

    # Setup pre-existing state
    existing_user = User(email="exists@example.com", first_name="Im", last_name="Here", hashed_password="hashed")
    db_session.add(existing_user)
    db_session.commit()

    request_data = RegisterRequest(
        user=UserCreate(email="exists@example.com", password="password123"),
        workspace=WorkspaceCreate(name="Ghost Corp", email="ghost@corp.com"),
        plan=PlanName.PRO,
    )

    with pytest.raises(UserExistsExceptionError):
        auth_service.register(request_data)


def test_onboard_exception_database_failure_triggers_rollback(db_session):
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
        plan=PlanName.PRO,
    )

    # Force an internal failure mid-flight by patching 'generate_token_pair' to raise a runtime error
    with patch("src.erp.api.auth.service.generate_token_pair", side_effect=ValueError("JWT Crypto System Error")):  # noqa: SIM117
        with pytest.raises(OnboardingFailedExceptionError):
            auth_service.register(request_data)

    # Assert that rollback successfully kept database clean of partial/orphaned items
    db_session.expire_all()
    assert db_session.query(User).filter_by(email="rollback@example.com").first() is None
    assert db_session.query(Workspace).filter_by(name="Rollback Inc").first() is None


#  ============================================================================
#  LOGIN SERVICE TESTS (`login`)
#  ============================================================================


def test_login_happy_path(db_session):
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
    db_session.flush()

    link = WorkspaceUser(
        user_id=user.id,
        workspace_id=workspace.id,
        role=WorkspaceRoleEnum.FULL_ADMIN,
        status=InvitationStatusEnum.ACTIVE,
    )
    db_session.add(link)
    db_session.commit()

    login_data = OAuth2PasswordRequestForm(username="login_ok@example.com", password=raw_password)

    response = auth_service.login(login_data)

    assert response.access_token is not None
    assert response.refresh_token is not None
    assert response.workspace_id == workspace.id

    # Assert stateful active session exists
    session = db_session.query(UserSession).filter_by(user_id=user.id).one()
    assert session is not None


def test_login_user_with_no_workspaces_raises_index_error(db_session):
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
    db_session.flush()

    login_data = OAuth2PasswordRequestForm(username="orphan@example.com", password=raw_password)

    with pytest.raises(IndexError):
        auth_service.login(login_data)


@pytest.mark.parametrize(
    "email, password",
    [
        ("exists_user@example.com", "incorrect_password"),
        ("missing_user@example.com", "any_password"),
        ("exists_user@example.com", ""),
    ],
)
def test_login_exception_invalid_credentials(db_session, email, password):
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
    db_session.flush()

    link = WorkspaceUser(
        user_id=user.id,
        workspace_id=workspace.id,
        role=WorkspaceRoleEnum.FULL_ADMIN,
        status=InvitationStatusEnum.ACTIVE,
    )
    db_session.add(link)
    db_session.flush()

    login_data = OAuth2PasswordRequestForm(username=email, password=password)

    with pytest.raises(CredentialsExceptionError):
        auth_service.login(login_data)


def test_login_purges_multiple_concurrent_sessions(db_session):
    """
    If a user has somehow accumulated multiple tracking sessions in the database,
    logging in must safely purge ALL old sessions to preserve strict single-active-session bounds.
    """
    auth_service = AuthService(db_session)
    raw_pw = "pass123"
    user = User(email="purge@example.com", first_name="P", last_name="U", hashed_password=get_password_hash(raw_pw))
    workspace = Workspace(name="Purge Corp", email="purge@corp.com")
    db_session.add_all([user, workspace])
    db_session.flush()

    link = WorkspaceUser(
        user_id=user.id,
        workspace_id=workspace.id,
        role=WorkspaceRoleEnum.FULL_ADMIN,
        status=InvitationStatusEnum.ACTIVE,
    )

    session_1 = UserSession(user_id=user.id, session_id="session-alpha", expires_at=datetime.now(UTC))
    session_2 = UserSession(user_id=user.id, session_id="session-beta", expires_at=datetime.now(UTC))

    db_session.add_all([link, session_1, session_2])
    db_session.flush()

    login_data = OAuth2PasswordRequestForm(username="purge@example.com", password=raw_pw)

    response = auth_service.login(login_data)
    assert response.workspace_id == workspace.id

    remaining_sessions = db_session.query(UserSession).filter_by(user_id=user.id).all()
    assert len(remaining_sessions) == 1
    assert remaining_sessions[0].session_id not in ["session-alpha", "session-beta"]


# ============================================================================
# LOGOUT SERVICE TESTS (`logout`)
# ============================================================================


def test_logout_happy_path(db_session):
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
    db_session.commit()
    db_session.refresh(user)

    tokens = generate_token_pair(user.id)
    payload = decode_token(tokens["refresh_token"])

    session = UserSession(
        user_id=user.id,
        session_id=payload["jti"],
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db_session.add(session)
    db_session.commit()

    auth_service.logout(tokens["refresh_token"])

    db_session.expire_all()

    assert db_session.query(UserSession).filter_by(session_id=payload["jti"]).first() is None


def test_logout_edge_case_token_missing_claims(db_session):
    """
    EDGE CASE:
    If a token payload is missing required identity claims, logout must safely return
    without attempting to delete any session.
    """
    auth_service = AuthService(db_session)

    with patch(
        "src.erp.api.auth.service.decode_token",
        return_value={"type": "refresh"},
    ):
        # Should not raise
        auth_service.logout("invalid-token-missing-claims")


def test_logout_silently_swallows_decoding_exceptions(db_session):
    """
    EXCEPTION PATH:
    If token decoding fails because the token is expired, forged, or malformed,
    logout must swallow the exception and return without leaking errors.
    """
    auth_service = AuthService(db_session)

    with patch(
        "src.erp.api.auth.service.decode_token",
        side_effect=Exception("Invalid token"),
    ):
        try:
            auth_service.logout("complete-garbage-token-string")
        except Exception as e:
            pytest.fail(f"Logout service leaked an exception path! Error: {e}")


# ============================================================================
# 4. REFRESH TOKEN SERVICE TESTS (`refresh_token`)
# ============================================================================


def test_refresh_token_happy_path(db_session):
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
    db_session.commit()
    db_session.refresh(user)

    tokens = generate_token_pair(user.id)
    payload = decode_token(tokens["refresh_token"])

    session = UserSession(
        user_id=user.id,
        session_id=payload["jti"],
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db_session.add(session)
    db_session.commit()

    new_access_token = auth_service.refresh_token(tokens["refresh_token"])

    assert new_access_token is not None


def test_refresh_token_exception_wrong_token_type(db_session):
    """
    If a client attempts to pass a short-lived 'access' token instead of a long-lived 'refresh'
    token into the validation pipeline, it must instantly raise a TokenInvalidError.
    """
    auth_service = AuthService(db_session)

    access_token = create_access_token(subject="user_123")

    with pytest.raises(TokenInvalidError):
        auth_service.refresh_token(access_token)


@pytest.mark.parametrize(
    "mock_payload",
    [
        {"type": "refresh", "jti": "missing-sub"},  # Missing subject field
        {"type": "refresh", "sub": "missing-jti"},  # Missing tracking ID field
        {"type": "refresh"},  # Missing both fields
    ],
)
def test_refresh_token_exception_missing_required_claims(db_session, mock_payload):
    """
    If a valid token payload fails basic validation checks because identity keys
    are missing from the payload dictionary structure, it must raise a TokenInvalidError.
    """
    auth_service = AuthService(db_session)

    with (
        patch("src.erp.api.auth.service.decode_token", return_value=mock_payload),
        pytest.raises(TokenInvalidError),
    ):
        auth_service.refresh_token("valid.token.payload")


def test_refresh_token_exception_session_revoked_or_overwritten(db_session):
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
    db_session.commit()
    db_session.refresh(user)

    tokens = generate_token_pair(user.id)

    with pytest.raises(TokenInvalidError):
        auth_service.refresh_token(tokens["refresh_token"])
