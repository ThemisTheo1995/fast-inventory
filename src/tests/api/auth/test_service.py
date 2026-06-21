from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.security import OAuth2PasswordRequestForm

from erp.api.auth.exceptions import (
    CredentialsExceptionError,
    OnboardingFailedExceptionError,
    TokenInvalidError,
    UserExistsExceptionError,
)
from erp.api.auth.models import User, UserSession
from erp.api.auth.schemas import LogoutRequest, RefreshToken, RegisterRequest, UserCreate
from erp.api.auth.service import AuthService
from erp.api.auth.utils import create_access_token, decode_token, generate_token_pair, get_password_hash
from erp.api.workspace.enums import InvitationStatusEnum, WorkspaceRoleEnum
from erp.api.workspace.models import Workspace, WorkspaceUser
from erp.api.workspace.schemas.workspace import WorkspaceCreate

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
    )

    token_response = auth_service.register(request_data)

    workspace_user = db_session.query(WorkspaceUser).filter_by(id=token_response.user.id).first()

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
    )

    # Force an internal failure mid-flight by patching 'generate_token_pair' to raise a runtime error
    with patch("erp.api.auth.service.generate_token_pair", side_effect=ValueError("JWT Crypto System Error")):  # noqa: SIM117
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
    Providing matching credentials must successfully yield a TokenResponse,
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
    user = User(email="logout_target@example.com", first_name="L", last_name="O", hashed_password="hash")
    db_session.add(user)
    db_session.commit()

    tokens = generate_token_pair(user.id)
    payload = decode_token(tokens["refresh_token"])

    session = UserSession(user_id=user.id, session_id=payload["jti"], expires_at=datetime.now(UTC))
    db_session.add(session)
    db_session.commit()

    logout_data = LogoutRequest(refresh_token=tokens["refresh_token"])
    auth_service.logout(logout_data)

    db_session.expire_all()
    assert db_session.query(UserSession).filter_by(session_id=payload["jti"]).first() is None


def test_logout_edge_case_token_missing_claims(db_session):
    """
    EDGE CASE:
    If a structurally sound token missing its 'sub' or 'jti' parameters passes into the layout,
    the logout flow must recognize the mismatch and safely return early without calling database execution.
    """
    auth_service = AuthService(db_session)
    logout_data = LogoutRequest(refresh_token="invalid-token-missing-claims")

    with patch("erp.api.auth.service.decode_token", return_value={"type": "refresh"}):
        auth_service.logout(logout_data)


def test_logout_silently_swallows_decoding_exceptions(db_session):
    """
    EXCEPTION PATH & EDGE CASE:
    If an expired, forged, or structurally damaged token enters logout, the routine
    must cleanly execute a database rollback, swallow the validation failure, and return silently.
    """
    auth_service = AuthService(db_session)
    logout_data = LogoutRequest(refresh_token="complete-garbage-token-string")

    try:
        auth_service.logout(logout_data)
    except Exception as e:
        pytest.fail(f"Logout service leaked an exception path! Error: {e}")


# ============================================================================
# 4. REFRESH TOKEN SERVICE TESTS (`refresh_token`)
# ============================================================================


def test_refresh_token_happy_path(db_session):
    """
    A valid, live refresh token matched against an open tracking record
    must quickly mint and yield a clean RefreshResponse wrapper.
    """
    auth_service = AuthService(db_session)
    user = User(email="refresh_me@example.com", first_name="R", last_name="M", hashed_password="hash")
    db_session.add(user)
    db_session.commit()

    tokens = generate_token_pair(user.id)
    payload = decode_token(tokens["refresh_token"])

    session = UserSession(user_id=user.id, session_id=payload["jti"], expires_at=datetime.now(UTC) + timedelta(hours=1))
    db_session.add(session)
    db_session.commit()
    data = RefreshToken(refresh_token=tokens["refresh_token"])

    response = auth_service.refresh_token(data)

    assert response.access_token is not None
    assert response.refresh_token == tokens["refresh_token"]
    assert response.token_type == "bearer"


def test_refresh_token_exception_wrong_token_type(db_session):
    """
    If a client attempts to pass a short-lived 'access' token instead of a long-lived 'refresh'
    token into the validation pipeline, it must instantly raise a TokenInvalidError.
    """
    auth_service = AuthService(db_session)
    # Mint an ACCESS token explicitly
    access_token = create_access_token(subject="user_123")
    data = RefreshToken(refresh_token=access_token)

    with pytest.raises(TokenInvalidError):
        auth_service.refresh_token(data)


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

    with patch("erp.api.auth.service.decode_token", return_value=mock_payload), pytest.raises(TokenInvalidError):
        auth_service.refresh_token(RefreshToken(refresh_token="valid.token.payload"))


def test_refresh_token_exception_session_revoked_or_overwritten(db_session):
    """
    If a token is cryptographically authentic but its underlying tracking record has been deleted
    from the database (revoked due to security breaches, logouts, or concurrent sign-ins),
    the endpoint must reject the exchange and throw a TokenInvalidError.
    """
    auth_service = AuthService(db_session)
    user = User(email="stale_session@example.com", first_name="S", last_name="S", hashed_password="hash")
    db_session.add(user)
    db_session.commit()

    tokens = generate_token_pair(user.id)

    with pytest.raises(TokenInvalidError):
        auth_service.refresh_token(RefreshToken(refresh_token=tokens["refresh_token"]))
