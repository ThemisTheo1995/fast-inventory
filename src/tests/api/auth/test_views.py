import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.api.auth.exceptions import TokenInvalidError
from erp.api.auth.models import User, UserSession
from erp.api.auth.utils import (
    generate_password_reset_token,
    generate_whitelist_token,
    get_password_hash,
)
from erp.api.pricing.enums import PlanName
from erp.api.pricing.models import PricingPlan
from erp.api.workspace.models import Workspace
from erp.api.workspace_user.enums import InvitationStatusEnum, WorkspaceRoleEnum
from erp.api.workspace_user.models import WorkspaceUser

# ==============================================================================
# TEST-ONLY FIXTURES
# ==============================================================================


@pytest_asyncio.fixture
async def existing_pricing_plan(db_session: AsyncSession) -> PricingPlan:
    result = await db_session.execute(select(PricingPlan).where(PricingPlan.name == PlanName.ENTERPRISE))
    return result.scalars().first()


@pytest_asyncio.fixture
async def pending_invited_user(
    db_session: AsyncSession,
    seed_workspace: uuid.UUID,
) -> User:
    """Seeds a user with a pending workspace invitation."""
    user = User(
        id=uuid.uuid4(),
        email=f"invited-{uuid.uuid4()}@example.com",
        first_name=None,
        last_name=None,
        hashed_password=None,
        is_deleted=False,
        is_whitelisted=True,
    )

    db_session.add(user)
    await db_session.flush()

    workspace_user = WorkspaceUser(
        id=uuid.uuid4(),
        user_id=user.id,
        workspace_id=seed_workspace,
        role=WorkspaceRoleEnum.READ_ONLY,
        status=InvitationStatusEnum.PENDING,
        is_deleted=False,
    )

    db_session.add(workspace_user)
    await db_session.commit()

    return user


@pytest_asyncio.fixture
async def auth_user(
    db_session: AsyncSession,
    seed_workspace: uuid.UUID,
) -> User:
    """
    Creates a dedicated authentication user.

    This deliberately does not reuse tst_user because tst_user is intended
    to be a lightweight general-purpose user fixture and does not contain
    a password hash.
    """
    user = User(
        id=uuid.uuid4(),
        email=f"auth-{uuid.uuid4()}@example.com",
        first_name="Auth",
        last_name="User",
        hashed_password=get_password_hash("TestPassword123!"),
        is_deleted=False,
        is_whitelisted=True,
    )

    db_session.add(user)
    await db_session.flush()

    workspace_user = WorkspaceUser(
        id=uuid.uuid4(),
        user_id=user.id,
        workspace_id=seed_workspace,
        role=WorkspaceRoleEnum.FULL_ADMIN,
        status=InvitationStatusEnum.ACTIVE,
        is_deleted=False,
    )

    db_session.add(workspace_user)
    await db_session.commit()
    await db_session.refresh(user)

    return user


def plan_value(existing_pricing_plan: PricingPlan) -> str:
    """Returns the string representation accepted by RegisterRequest."""
    return (
        existing_pricing_plan.name.value if hasattr(existing_pricing_plan.name, "value") else existing_pricing_plan.name
    )


def registration_payload(
    existing_pricing_plan: PricingPlan,
    *,
    user_email: str = "new-user@example.com",
    workspace_email: str = "new-workspace@example.com",
) -> dict:
    """Builds a valid registration payload."""
    return {
        "user": {
            "email": user_email,
            "password": "TestPassword123!",
            "first_name": "New",
            "last_name": "User",
        },
        "workspace": {
            "name": "New Test Workspace",
            "email": workspace_email,
        },
        "plan": plan_value(existing_pricing_plan),
    }


# ==============================================================================
# VERIFY
# ==============================================================================


async def test_verify_success(
    client,
    db_session,
    tst_user,
):
    """Verifies a valid whitelist token through the real AuthService."""
    tst_user.is_whitelisted = False
    await db_session.commit()

    token = generate_whitelist_token(tst_user.id)

    response = await client.post(
        "/auth/verify",
        params={"token": token},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"detail": "Account successfully whitelisted. You may now log in."}

    await db_session.refresh(tst_user)

    assert tst_user.is_whitelisted is True


async def test_verify_already_whitelisted(
    client,
    tst_user,
):
    """Verifies an already-whitelisted user can be verified again."""
    token = generate_whitelist_token(tst_user.id)

    response = await client.post(
        "/auth/verify",
        params={"token": token},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"detail": "Account successfully whitelisted. You may now log in."}


async def test_verify_user_not_found(client):
    """Verifies a valid token for a nonexistent user returns 404."""
    token = generate_whitelist_token(uuid.uuid4())

    response = await client.post(
        "/auth/verify",
        params={"token": token},
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_verify_invalid_token(client):
    """Verifies malformed whitelist tokens are rejected."""
    response = await client.post(
        "/auth/verify",
        params={"token": "invalid-token"},
    )

    assert response.status_code in {
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
    }


async def test_verify_missing_token(client):
    """Verifies token is required."""
    response = await client.post("/auth/verify")

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# ==============================================================================
# REGISTER
# ==============================================================================


async def test_register_success(
    client,
    db_session,
    existing_pricing_plan,
):
    user_email = f"register-{uuid.uuid4()}@example.com"
    workspace_email = f"workspace-{uuid.uuid4()}@example.com"

    response = await client.post(
        "/auth/register",
        json=registration_payload(
            existing_pricing_plan,
            user_email=user_email,
            workspace_email=workspace_email,
        ),
    )

    assert response.status_code == status.HTTP_201_CREATED

    data = response.json()

    assert data["workspace_id"]
    assert data["is_whitelisted"] is False

    workspace_result = await db_session.execute(
        select(Workspace).where(
            Workspace.id == uuid.UUID(data["workspace_id"]),
        )
    )
    workspace = workspace_result.scalar_one()

    assert workspace.name == "New Test Workspace"
    assert workspace.email == workspace_email

    user_result = await db_session.execute(select(User).where(User.email == user_email))
    user = user_result.scalar_one()

    assert user.email == user_email
    assert user.first_name == "New"
    assert user.last_name == "User"
    assert user.hashed_password is not None
    assert user.is_whitelisted is False

    workspace_user_result = await db_session.execute(
        select(WorkspaceUser).where(
            WorkspaceUser.user_id == user.id,
            WorkspaceUser.workspace_id == workspace.id,
        )
    )
    workspace_user = workspace_user_result.scalar_one()

    assert workspace_user.role == WorkspaceRoleEnum.FULL_ADMIN
    assert workspace_user.status == InvitationStatusEnum.ACTIVE


async def test_register_duplicate_user(
    client,
    tst_user,
    existing_pricing_plan,
):
    """Verifies registration rejects an existing user."""
    payload = registration_payload(
        existing_pricing_plan,
        user_email=tst_user.email,
        workspace_email=f"new-workspace-{uuid.uuid4()}@example.com",
    )

    response = await client.post(
        "/auth/register",
        json=payload,
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_register_duplicate_workspace(
    client,
    db_session,
    seed_workspace,
    existing_pricing_plan,
):
    """Verifies registration rejects an existing workspace email."""
    result = await db_session.execute(
        select(Workspace).where(
            Workspace.id == seed_workspace,
        )
    )
    workspace = result.scalar_one()

    payload = registration_payload(
        existing_pricing_plan,
        user_email=f"new-user-{uuid.uuid4()}@example.com",
        workspace_email=workspace.email,
    )

    response = await client.post(
        "/auth/register",
        json=payload,
    )

    assert response.status_code == status.HTTP_409_CONFLICT


async def test_register_nonexistent_plan(client):
    """Verifies invalid plan values are rejected by schema validation."""
    payload = {
        "user": {
            "email": f"register-{uuid.uuid4()}@example.com",
            "password": "TestPassword123!",
            "first_name": "New",
            "last_name": "User",
        },
        "workspace": {
            "name": "New Test Workspace",
            "email": f"workspace-{uuid.uuid4()}@example.com",
        },
        "plan": "definitely-not-a-real-plan",
    }

    response = await client.post(
        "/auth/register",
        json=payload,
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_register_missing_required_fields(client):
    """Verifies RegisterRequest validation."""
    response = await client.post(
        "/auth/register",
        json={},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_register_extra_field_rejected(
    client,
    existing_pricing_plan,
):
    """Verifies RegisterRequest forbids unknown top-level fields."""
    payload = registration_payload(existing_pricing_plan)
    payload["unexpected"] = "not allowed"

    response = await client.post(
        "/auth/register",
        json=payload,
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# ==============================================================================
# ONBOARD
# ==============================================================================


async def test_onboard_success(
    client,
    db_session,
    pending_invited_user,
):
    """Verifies a pending invitation is fully onboarded."""
    response = await client.post(
        "/auth/onboard",
        json={
            "email": pending_invited_user.email,
            "password": "NewPassword123!",
            "first_name": "Invited",
            "last_name": "Person",
        },
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert data["workspace_id"]
    assert data["is_whitelisted"] is True

    cookies = response.headers.get_list("set-cookie")

    assert any("access_token=" in cookie for cookie in cookies)
    assert any("refresh_token=" in cookie for cookie in cookies)

    await db_session.refresh(pending_invited_user)

    assert pending_invited_user.hashed_password is not None
    assert pending_invited_user.first_name == "Invited"
    assert pending_invited_user.last_name == "Person"

    workspace_user_result = await db_session.execute(
        select(WorkspaceUser).where(
            WorkspaceUser.user_id == pending_invited_user.id,
        )
    )

    workspace_user = workspace_user_result.scalar_one()

    assert workspace_user.status == InvitationStatusEnum.ACTIVE


async def test_onboard_unknown_user(client):
    """Verifies onboarding rejects an unknown email."""
    response = await client.post(
        "/auth/onboard",
        json={
            "email": "does-not-exist@example.com",
            "password": "NewPassword123!",
            "first_name": "Unknown",
            "last_name": "User",
        },
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_onboard_already_onboarded_user(
    client,
    tst_user,
):
    """Verifies onboarding rejects an existing user without a pending invitation."""
    response = await client.post(
        "/auth/onboard",
        json={
            "email": tst_user.email,
            "password": "AnotherPassword123!",
            "first_name": "Changed",
            "last_name": "Name",
        },
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_onboard_missing_required_fields(client):
    """Verifies onboarding requires the expected UserCreate fields."""
    response = await client.post(
        "/auth/onboard",
        json={},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# ==============================================================================
# LOGIN
# ==============================================================================


async def test_login_success(
    client,
    auth_user,
):
    """Verifies successful login using a dedicated password-bearing user."""
    response = await client.post(
        "/auth/login",
        data={
            "username": auth_user.email,
            "password": "TestPassword123!",
        },
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert data["workspace_id"]
    assert data["is_whitelisted"] is True

    cookies = response.headers.get_list("set-cookie")

    assert any("access_token=" in cookie for cookie in cookies)
    assert any("refresh_token=" in cookie for cookie in cookies)


async def test_login_wrong_password(
    client,
    auth_user,
):
    """Verifies incorrect passwords are rejected."""
    response = await client.post(
        "/auth/login",
        data={
            "username": auth_user.email,
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_login_unknown_user(client):
    """Verifies unknown users are rejected."""
    response = await client.post(
        "/auth/login",
        data={
            "username": "unknown-user@example.com",
            "password": "TestPassword123!",
        },
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_login_not_whitelisted(
    client,
    db_session,
    auth_user,
):
    """Verifies an unwhitelisted user cannot log in."""
    auth_user.is_whitelisted = False
    await db_session.commit()

    response = await client.post(
        "/auth/login",
        data={
            "username": auth_user.email,
            "password": "TestPassword123!",
        },
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_login_missing_form_fields(client):
    """Verifies OAuth2 form fields are required."""
    response = await client.post(
        "/auth/login",
        data={},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# ==============================================================================
# LOGOUT
# ==============================================================================


async def test_logout_with_refresh_token(
    client,
    auth_user,
):
    """Verifies logout revokes the real refresh session."""
    login_response = await client.post(
        "/auth/login",
        data={
            "username": auth_user.email,
            "password": "TestPassword123!",
        },
    )

    assert login_response.status_code == status.HTTP_200_OK

    response = await client.post("/auth/logout")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"detail": "Successfully logged out"}

    cookies = response.headers.get_list("set-cookie")

    assert any("access_token=" in cookie for cookie in cookies)
    assert any("refresh_token=" in cookie for cookie in cookies)
    assert any("Max-Age=0" in cookie for cookie in cookies)


async def test_logout_without_refresh_token(client):
    """Verifies logout succeeds even when no refresh cookie exists."""
    client.cookies.clear()

    response = await client.post("/auth/logout")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"detail": "Successfully logged out"}


# ==============================================================================
# REFRESH
# ==============================================================================


async def test_refresh_success(
    client,
    auth_user,
):
    """Verifies a real refresh token produces a new access token."""
    login_response = await client.post(
        "/auth/login",
        data={
            "username": auth_user.email,
            "password": "TestPassword123!",
        },
    )

    assert login_response.status_code == status.HTTP_200_OK

    refresh_token = login_response.cookies.get("refresh_token")
    assert refresh_token is not None

    client.cookies.set("refresh_token", refresh_token)

    response = await client.post("/auth/refresh")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"detail": "Access token refreshed"}

    cookies = response.headers.get_list("set-cookie")
    assert any("access_token=" in cookie for cookie in cookies)


async def test_refresh_without_token(client):
    """Verifies refresh requires a refresh token."""
    client.cookies.clear()

    response = await client.post("/auth/refresh")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {"detail": "Refresh token missing or blocked by browser"}


async def test_refresh_invalid_token(client):
    """
    Verifies malformed refresh tokens are rejected.

    AuthService raises TokenInvalidError and the current application does
    not convert this exception into an HTTP response, so ASGITransport
    propagates the exception to the test.
    """
    client.cookies.clear()
    client.cookies.set(
        "refresh_token",
        "not-a-valid-refresh-token",
    )

    with pytest.raises(TokenInvalidError):
        await client.post("/auth/refresh")


# ==============================================================================
# PASSWORD RESET REQUEST
# ==============================================================================


async def test_request_password_reset_existing_user(
    client,
    tst_user,
):
    """Verifies password reset request for an existing user."""
    response = await client.post(
        "/auth/request-password-reset",
        json={
            "email": tst_user.email,
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"detail": "If an account with that email exists, a password reset link has been sent."}


async def test_request_password_reset_unknown_email(client):
    """Verifies password reset uses anti-enumeration behaviour."""
    response = await client.post(
        "/auth/request-password-reset",
        json={
            "email": "unknown-password-reset@example.com",
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"detail": "If an account with that email exists, a password reset link has been sent."}


async def test_request_password_reset_cooldown(
    client,
    db_session,
    tst_user,
):
    """Verifies reset requests inside the cooldown are silently ignored."""
    tst_user.last_password_reset_sent_at = datetime.now(UTC)

    await db_session.commit()

    response = await client.post(
        "/auth/request-password-reset",
        json={
            "email": tst_user.email,
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"detail": "If an account with that email exists, a password reset link has been sent."}


async def test_request_password_reset_invalid_email(client):
    """Verifies EmailStr validation."""
    response = await client.post(
        "/auth/request-password-reset",
        json={
            "email": "not-an-email",
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_request_password_reset_missing_email(client):
    """Verifies email is required."""
    response = await client.post(
        "/auth/request-password-reset",
        json={},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# ==============================================================================
# RESET PASSWORD
# ==============================================================================


async def test_reset_password_success(
    client,
    db_session,
    auth_user,
):
    """Verifies password reset changes the password and revokes sessions."""
    session = UserSession(
        id=uuid.uuid4(),
        user_id=auth_user.id,
        session_id=str(uuid.uuid4()),
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )

    db_session.add(session)
    await db_session.commit()

    token = generate_password_reset_token(auth_user.id)

    response = await client.post(
        "/auth/reset-password",
        json={
            "token": token,
            "new_password": "NewPassword123!",
        },
    )

    assert response.status_code == status.HTTP_200_OK

    assert response.json() == {"detail": "Password successfully reset. You may now log in with your new password."}

    cookies = response.headers.get_list("set-cookie")

    assert any("access_token=" in cookie for cookie in cookies)
    assert any("refresh_token=" in cookie for cookie in cookies)

    session_result = await db_session.execute(
        select(UserSession).where(
            UserSession.user_id == auth_user.id,
        )
    )

    assert session_result.scalar_one_or_none() is None

    await db_session.refresh(auth_user)

    response = await client.post(
        "/auth/login",
        data={
            "username": auth_user.email,
            "password": "TestPassword123!",
        },
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_reset_password_unknown_user(client):
    """Verifies a reset token belonging to a nonexistent user is rejected."""
    token = generate_password_reset_token(uuid.uuid4())

    response = await client.post(
        "/auth/reset-password",
        json={
            "token": token,
            "new_password": "NewPassword123!",
        },
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_reset_password_invalid_token(client):
    """Verifies malformed password reset tokens are rejected."""
    response = await client.post(
        "/auth/reset-password",
        json={
            "token": "not-a-valid-reset-token",
            "new_password": "NewPassword123!",
        },
    )

    assert response.status_code in {
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
    }


async def test_reset_password_short_password(client):
    """Verifies PasswordResetConfirm enforces minimum password length."""
    response = await client.post(
        "/auth/reset-password",
        json={
            "token": "anything",
            "new_password": "short",
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_reset_password_missing_fields(client):
    """Verifies both reset fields are required."""
    response = await client.post(
        "/auth/reset-password",
        json={},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
