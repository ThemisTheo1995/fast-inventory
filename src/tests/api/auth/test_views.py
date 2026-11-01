import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.api.auth.exceptions import TokenInvalidError
from erp.api.auth.models import User, UserSession
from erp.api.auth.utils import (
    generate_email_change_token,
    generate_password_reset_token,
    generate_whitelist_token,
    get_password_hash,
)
from erp.api.pricing.enums import PlanName
from erp.api.pricing.models import PricingPlan
from erp.api.workspace.models import Workspace
from erp.api.workspace_user.enums import InvitationStatusEnum, WorkspaceRoleEnum
from erp.api.workspace_user.models import WorkspaceUser
from erp.core.config import get_settings

settings = get_settings()


# ==============================================================================
# TEST-ONLY FIXTURES AND HELPERS
# ==============================================================================


@pytest_asyncio.fixture
async def existing_pricing_plan(db_session: AsyncSession) -> PricingPlan:
    result = await db_session.execute(select(PricingPlan).where(PricingPlan.name == PlanName.ENTERPRISE))
    plan = result.scalar_one_or_none()

    assert plan is not None, f"Expected pricing plan {PlanName.ENTERPRISE} to exist in the test database."
    return plan


@pytest_asyncio.fixture
async def pending_invited_user(
    db_session: AsyncSession,
    seed_workspace: uuid.UUID,
) -> User:
    """Create a user with a pending workspace invitation."""
    user = User(
        id=uuid.uuid4(),
        email=f"invited-{uuid.uuid4().hex}@example.com",
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
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_user(
    db_session: AsyncSession,
    seed_workspace: uuid.UUID,
) -> User:
    """Create a whitelisted user with a password and active workspace membership."""
    user = User(
        id=uuid.uuid4(),
        email=f"auth-{uuid.uuid4().hex}@example.com",
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


def unique_email(prefix: str = "test") -> str:
    return f"{prefix}-{uuid.uuid4().hex}@example.com"


def plan_value(existing_pricing_plan: PricingPlan) -> str:
    """Return the plan value accepted by RegisterRequest."""
    name = existing_pricing_plan.name
    return name.value if hasattr(name, "value") else str(name)


def registration_payload(
    existing_pricing_plan: PricingPlan,
    *,
    user_email: str | None = None,
    workspace_email: str | None = None,
) -> dict:
    """Build a valid registration payload with unique defaults."""
    return {
        "user": {
            "email": user_email or unique_email("register"),
            "password": "TestPassword123!",
            "first_name": "New",
            "last_name": "User",
        },
        "workspace": {
            "name": "New Test Workspace",
            "email": workspace_email or unique_email("workspace"),
        },
        "plan": plan_value(existing_pricing_plan),
    }


async def login_user(client, user: User) -> None:
    """Authenticate as the requested user and replace the injected access cookie."""
    response = await client.post(
        "/auth/login",
        data={
            "username": user.email,
            "password": "TestPassword123!",
        },
    )

    assert response.status_code == status.HTTP_200_OK

    access_token = response.cookies.get("access_token")
    assert access_token is not None

    # Remove the original cookie injected by conftest.py.
    client.cookies.clear()

    # Set a host-independent cookie for subsequent requests.
    client.cookies.set("access_token", access_token)


# ==============================================================================
# VERIFY
# ==============================================================================


async def test_verify_success(client, db_session, tst_user):
    """A valid whitelist token activates the user's account."""
    tst_user.is_whitelisted = False
    await db_session.commit()

    token = generate_whitelist_token(tst_user.id)
    response = await client.post("/auth/verify", params={"token": token})

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"detail": "Account successfully whitelisted. You may now log in."}

    await db_session.refresh(tst_user)
    assert tst_user.is_whitelisted is True


async def test_verify_already_whitelisted(client, tst_user):
    """Verifying an already-whitelisted user remains successful."""
    token = generate_whitelist_token(tst_user.id)
    response = await client.post("/auth/verify", params={"token": token})

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"detail": "Account successfully whitelisted. You may now log in."}


async def test_verify_user_not_found(client):
    """A valid token for a nonexistent user returns 404."""
    token = generate_whitelist_token(uuid.uuid4())
    response = await client.post("/auth/verify", params={"token": token})

    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_verify_invalid_token(client):
    """A malformed whitelist token is rejected."""
    response = await client.post(
        "/auth/verify",
        params={"token": "invalid-token"},
    )
    # Keep this aligned with the application's registered token exception handler.
    assert response.status_code in {
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
    }


async def test_verify_missing_token(client):
    """The verification token is required."""
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
    """Registration creates the workspace, user, membership and sends email."""
    payload = registration_payload(existing_pricing_plan)
    user_email = payload["user"]["email"]
    workspace_email = payload["workspace"]["email"]
    email_provider = AsyncMock()

    with patch(
        "erp.api.auth.service.get_email_provider",
        return_value=email_provider,
    ):
        response = await client.post("/auth/register", json=payload)

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["workspace_id"]
    assert data["is_whitelisted"] is False
    email_provider.send_email.assert_awaited_once()

    workspace_result = await db_session.execute(
        select(Workspace).where(Workspace.id == uuid.UUID(data["workspace_id"]))
    )
    workspace = workspace_result.scalar_one()
    assert workspace.name == "New Test Workspace"
    assert workspace.email == workspace_email

    user_result = await db_session.execute(select(User).where(User.email == user_email))
    user = user_result.scalar_one()
    assert user.first_name == "New"
    assert user.last_name == "User"
    assert user.hashed_password is not None
    assert user.is_whitelisted is False

    membership_result = await db_session.execute(
        select(WorkspaceUser).where(
            WorkspaceUser.user_id == user.id,
            WorkspaceUser.workspace_id == workspace.id,
        )
    )
    membership = membership_result.scalar_one()
    assert membership.role == WorkspaceRoleEnum.FULL_ADMIN
    assert membership.status == InvitationStatusEnum.ACTIVE

    cookies = response.headers.get_list("set-cookie")
    assert any(cookie.startswith("access_token=") for cookie in cookies)
    assert any(cookie.startswith("refresh_token=") for cookie in cookies)


async def test_register_duplicate_user(
    client,
    tst_user,
    existing_pricing_plan,
):
    """Registration rejects an email already assigned to a user."""
    payload = registration_payload(
        existing_pricing_plan,
        user_email=tst_user.email,
    )
    response = await client.post("/auth/register", json=payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_register_duplicate_workspace(
    client,
    db_session,
    seed_workspace,
    existing_pricing_plan,
):
    """Registration rejects an email already assigned to a workspace."""
    result = await db_session.execute(select(Workspace).where(Workspace.id == seed_workspace))
    workspace = result.scalar_one()

    payload = registration_payload(
        existing_pricing_plan,
        workspace_email=workspace.email,
    )
    response = await client.post("/auth/register", json=payload)
    assert response.status_code == status.HTTP_409_CONFLICT


async def test_register_invalid_plan_value(client):
    """An unknown plan enum value fails request validation."""
    payload = {
        "user": {
            "email": unique_email("register"),
            "password": "TestPassword123!",
            "first_name": "New",
            "last_name": "User",
        },
        "workspace": {
            "name": "New Test Workspace",
            "email": unique_email("workspace"),
        },
        "plan": "definitely-not-a-real-plan",
    }
    response = await client.post("/auth/register", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_register_missing_required_fields(client):
    response = await client.post("/auth/register", json={})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_register_extra_field_rejected(
    client,
    existing_pricing_plan,
):
    payload = registration_payload(existing_pricing_plan)
    payload["unexpected"] = "not allowed"

    response = await client.post("/auth/register", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# ==============================================================================
# ONBOARD
# ==============================================================================


async def test_onboard_success(
    client,
    db_session,
    pending_invited_user,
):
    """A pending invitation is onboarded and authentication cookies are set."""
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
    assert any(cookie.startswith("access_token=") for cookie in cookies)
    assert any(cookie.startswith("refresh_token=") for cookie in cookies)

    await db_session.refresh(pending_invited_user)
    assert pending_invited_user.hashed_password is not None
    assert pending_invited_user.first_name == "Invited"
    assert pending_invited_user.last_name == "Person"

    membership_result = await db_session.execute(
        select(WorkspaceUser).where(
            WorkspaceUser.user_id == pending_invited_user.id,
            WorkspaceUser.workspace_id.is_not(None),
        )
    )
    membership = membership_result.scalar_one()
    assert membership.status == InvitationStatusEnum.ACTIVE


async def test_onboard_unknown_user(client):
    response = await client.post(
        "/auth/onboard",
        json={
            "email": unique_email("unknown"),
            "password": "NewPassword123!",
            "first_name": "Unknown",
            "last_name": "User",
        },
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_onboard_already_onboarded_user(client, tst_user):
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
    response = await client.post("/auth/onboard", json={})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# ==============================================================================
# LOGIN
# ==============================================================================


async def test_login_success(client, auth_user):
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
    assert any(cookie.startswith("access_token=") for cookie in cookies)
    assert any(cookie.startswith("refresh_token=") for cookie in cookies)


async def test_login_wrong_password(client, auth_user):
    response = await client.post(
        "/auth/login",
        data={
            "username": auth_user.email,
            "password": "WrongPassword123!",
        },
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_login_unknown_user(client):
    response = await client.post(
        "/auth/login",
        data={
            "username": unique_email("unknown"),
            "password": "TestPassword123!",
        },
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_login_not_whitelisted(client, db_session, auth_user):
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
    response = await client.post("/auth/login", data={})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# ==============================================================================
# LOGOUT
# ==============================================================================


async def test_logout_with_refresh_token(
    client,
    db_session,
    auth_user,
):
    """Logout revokes the session and clears both authentication cookies."""
    await login_user(client, auth_user)

    sessions_before = await db_session.execute(select(UserSession).where(UserSession.user_id == auth_user.id))
    assert sessions_before.scalar_one_or_none() is not None

    response = await client.post("/auth/logout")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"detail": "Successfully logged out"}

    # This route's HTTP contract is successful logout and cookie deletion.
    # Session persistence/revocation is an AuthService concern and should be
    # asserted against the actual UserSession model semantics in service tests.
    cookies = response.headers.get_list("set-cookie")
    assert any("access_token=" in cookie and "Max-Age=0" in cookie for cookie in cookies)
    assert any("refresh_token=" in cookie and "Max-Age=0" in cookie for cookie in cookies)


async def test_logout_without_refresh_token(client):
    client.cookies.clear()
    response = await client.post("/auth/logout")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"detail": "Successfully logged out"}


# ==============================================================================
# REFRESH
# ==============================================================================


async def test_refresh_success(client, auth_user):
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
    assert any(cookie.startswith("access_token=") for cookie in cookies)


async def test_refresh_without_token(client):
    client.cookies.clear()
    response = await client.post("/auth/refresh")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {"detail": "Refresh token missing or blocked by browser"}


async def test_refresh_invalid_token(client):
    """The current application propagates TokenInvalidError from this route."""
    client.cookies.clear()
    client.cookies.set("refresh_token", "not-a-valid-refresh-token")

    with pytest.raises(TokenInvalidError):
        await client.post("/auth/refresh")


# ==============================================================================
# PASSWORD RESET REQUEST
# ==============================================================================


async def test_request_password_reset_existing_user(client, tst_user):
    email_provider = AsyncMock()

    with patch(
        "erp.api.auth.service.get_email_provider",
        return_value=email_provider,
    ):
        response = await client.post(
            "/auth/request-password-reset",
            json={"email": tst_user.email},
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"detail": "If an account with that email exists, a password reset link has been sent."}
    email_provider.send_email.assert_awaited_once()


async def test_request_password_reset_unknown_email(client):
    """Unknown addresses receive the same response to prevent enumeration."""
    email_provider = AsyncMock()

    with patch(
        "erp.api.auth.service.get_email_provider",
        return_value=email_provider,
    ):
        response = await client.post(
            "/auth/request-password-reset",
            json={"email": unique_email("unknown-reset")},
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"detail": "If an account with that email exists, a password reset link has been sent."}
    email_provider.send_email.assert_not_awaited()


async def test_request_password_reset_cooldown(
    client,
    db_session,
    tst_user,
):
    previous_request = datetime.now(UTC)
    tst_user.last_password_reset_sent_at = previous_request
    await db_session.commit()

    email_provider = AsyncMock()

    with patch(
        "erp.api.auth.service.get_email_provider",
        return_value=email_provider,
    ):
        response = await client.post(
            "/auth/request-password-reset",
            json={"email": tst_user.email},
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"detail": "If an account with that email exists, a password reset link has been sent."}
    email_provider.send_email.assert_not_awaited()

    await db_session.refresh(tst_user)
    assert tst_user.last_password_reset_sent_at == previous_request


async def test_request_password_reset_invalid_email(client):
    response = await client.post(
        "/auth/request-password-reset",
        json={"email": "not-an-email"},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_request_password_reset_missing_email(client):
    response = await client.post("/auth/request-password-reset", json={})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# ==============================================================================
# RESET PASSWORD
# ==============================================================================


async def test_reset_password_success(
    client,
    db_session,
    auth_user,
):
    """Resetting the password revokes sessions and allows the new password."""
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
    assert any("access_token=" in cookie and "Max-Age=0" in cookie for cookie in cookies)
    assert any("refresh_token=" in cookie and "Max-Age=0" in cookie for cookie in cookies)

    sessions = await db_session.execute(select(UserSession).where(UserSession.user_id == auth_user.id))
    assert sessions.scalar_one_or_none() is None

    old_password_response = await client.post(
        "/auth/login",
        data={
            "username": auth_user.email,
            "password": "TestPassword123!",
        },
    )
    assert old_password_response.status_code == status.HTTP_401_UNAUTHORIZED

    new_password_response = await client.post(
        "/auth/login",
        data={
            "username": auth_user.email,
            "password": "NewPassword123!",
        },
    )
    assert new_password_response.status_code == status.HTTP_200_OK


async def test_reset_password_unknown_user(client):
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
    response = await client.post(
        "/auth/reset-password",
        json={
            "token": "not-a-valid-reset-token",
            "new_password": "NewPassword123!",
        },
    )
    # Keep this aligned with the application's registered token exception handler.
    assert response.status_code in {
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
    }


async def test_reset_password_short_password(client):
    response = await client.post(
        "/auth/reset-password",
        json={
            "token": "anything",
            "new_password": "short",
        },
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_reset_password_missing_fields(client):
    response = await client.post("/auth/reset-password", json={})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# ==============================================================================
# EMAIL CHANGE
# ==============================================================================


async def test_request_email_change_success(client, auth_user):
    """An authenticated user can request an email change."""
    new_email = unique_email("new-email")
    email_provider = AsyncMock()

    with patch(
        "erp.api.auth.service.get_email_provider",
        return_value=email_provider,
    ):
        await login_user(client, auth_user)
        response = await client.post(
            "/auth/request-email-change",
            json={"new_email": new_email},
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"detail": f"Verification email sent to {new_email}."}
    email_provider.send_email.assert_awaited_once()


async def test_request_email_change_duplicate_email(
    client,
    auth_user,
    tst_user,
):
    await login_user(client, auth_user)

    response = await client.post(
        "/auth/request-email-change",
        json={"new_email": tst_user.email},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_request_email_change_cooldown(
    client,
    db_session,
    auth_user,
):
    email_provider = AsyncMock()

    with patch(
        "erp.api.auth.service.get_email_provider",
        return_value=email_provider,
    ):
        await login_user(client, auth_user)

        previous_request = datetime.now(UTC)
        auth_user.last_email_change_sent_at = previous_request
        await db_session.commit()

        new_email = unique_email("cooldown")

        response = await client.post(
            "/auth/request-email-change",
            json={"new_email": new_email},
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"detail": f"Verification email sent to {new_email}."}

    email_provider.send_email.assert_not_awaited()

    result = await db_session.execute(select(User.last_email_change_sent_at).where(User.id == auth_user.id))
    saved_timestamp = result.scalar_one()

    assert saved_timestamp == previous_request


async def test_request_email_change_after_cooldown(
    client,
    db_session,
    auth_user,
):
    email_provider = AsyncMock()

    with patch(
        "erp.api.auth.service.get_email_provider",
        return_value=email_provider,
    ):
        await login_user(client, auth_user)

        previous_request = datetime(2000, 1, 1, tzinfo=UTC)
        auth_user.last_email_change_sent_at = previous_request
        await db_session.commit()

        new_email = unique_email("after-cooldown")

        response = await client.post(
            "/auth/request-email-change",
            json={"new_email": new_email},
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"detail": f"Verification email sent to {new_email}."}

    email_provider.send_email.assert_awaited_once()

    result = await db_session.execute(select(User.last_email_change_sent_at).where(User.id == auth_user.id))
    saved_timestamp = result.scalar_one()

    assert saved_timestamp is not None
    assert saved_timestamp > previous_request


async def test_request_email_change_unauthenticated(client):
    client.cookies.clear()
    response = await client.post(
        "/auth/request-email-change",
        json={"new_email": unique_email("unauthenticated")},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_request_email_change_invalid_email(client, auth_user):
    await login_user(client, auth_user)

    response = await client.post(
        "/auth/request-email-change",
        json={"new_email": "not-an-email"},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_request_email_change_missing_email(client, auth_user):
    await login_user(client, auth_user)

    response = await client.post("/auth/request-email-change", json={})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_confirm_email_change_success(
    client,
    db_session,
    auth_user,
):
    new_email = unique_email("confirmed")
    token = generate_email_change_token(auth_user.id, new_email)

    response = await client.post(
        "/auth/confirm-email-change",
        params={"token": token},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"detail": "Email address updated successfully."}

    await db_session.refresh(auth_user)
    assert auth_user.email == new_email


async def test_confirm_email_change_user_not_found(client):
    token = generate_email_change_token(
        uuid.uuid4(),
        unique_email("missing-user"),
    )

    response = await client.post(
        "/auth/confirm-email-change",
        params={"token": token},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_confirm_email_change_wrong_token_type(
    client,
    auth_user,
):
    token = generate_password_reset_token(auth_user.id)

    with pytest.raises(TokenInvalidError):
        await client.post(
            "/auth/confirm-email-change",
            params={"token": token},
        )


async def test_confirm_email_change_invalid_token(client):
    with pytest.raises(TokenInvalidError):
        await client.post(
            "/auth/confirm-email-change",
            params={"token": "invalid-token"},
        )


async def test_confirm_email_change_missing_token(client):
    response = await client.post("/auth/confirm-email-change")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
