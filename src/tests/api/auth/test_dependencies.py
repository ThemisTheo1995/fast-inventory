import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from src.erp.api.auth.dependencies import get_current_user, get_current_workspace_user
from src.erp.api.auth.exceptions import CredentialsExceptionError
from src.erp.api.auth.models import User
from src.erp.api.auth.utils import get_password_hash
from src.erp.api.workspace.models import Workspace
from src.erp.api.workspace_user.enums import InvitationStatusEnum
from src.erp.api.workspace_user.exceptions import WorkspaceUserNotFoundError
from src.erp.api.workspace_user.models import WorkspaceUser
from src.erp.core.config import get_settings
from src.erp.core.exception_handlers import custom_app_error_handler
from src.erp.core.exceptions import BaseAppError
from src.erp.database.base import get_db

settings = get_settings()
SECRET_KEY = settings.AUTH_SECRET_KEY
ALGORITHM = settings.AUTH_ALGORITHM

# ============================================================================
# DUMMY FASTAPI APP FOR INTEGRATION TESTING
# ============================================================================

app = FastAPI()
app.add_exception_handler(BaseAppError, custom_app_error_handler)


@app.get("/test-user")
def mock_user_endpoint(current_user: Annotated[User, Depends(get_current_user)]):
    return {"id": str(current_user.id), "email": current_user.email}


@app.get("/test-active-user/{workspace_id}")
def mock_active_user_endpoint(workspace_user: Annotated[WorkspaceUser, Depends(get_current_workspace_user)]):
    return {
        "id": str(workspace_user.id),
        "user_id": str(workspace_user.user_id),
        "workspace_id": str(workspace_user.workspace_id),
        "role": workspace_user.role,
        "status": workspace_user.status,
    }


# ============================================================================
# HELPER FIXTURES
# ============================================================================


@pytest_asyncio.fixture
async def test_client(db_session):
    """Creates an AsyncClient and overrides the global 'get_db' dependency."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def create_jwt():
    """Helper tool to encode valid/invalid testing tokens."""

    def _encode(
        user_id: str | uuid.UUID,
        token_type: str = "access",
        expires_delta: timedelta | None = None,
    ):
        expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=15))
        payload = {
            "sub": str(user_id),
            "type": token_type,
            "exp": expire.timestamp(),
        }
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    return _encode


@pytest_asyncio.fixture
async def persisted_user(db_session):
    """Creates and flushes a baseline user into the test database."""
    user = User(
        id=uuid.uuid4(),
        email="dep_test@example.com",
        first_name="Dep",
        last_name="Tester",
        hashed_password=get_password_hash("secure_pass"),
    )
    db_session.add(user)
    await db_session.flush()
    return user


# ============================================================================
# 1. DIRECT UNIT TESTS FOR DEPENDENCY FUNCTIONS (Guarantees Line Coverage)
# ============================================================================


@pytest.mark.asyncio
async def test_get_current_user_direct_happy_path(db_session, create_jwt, persisted_user):
    """Directly calls get_current_user to reliably cover return user."""
    token = create_jwt(user_id=persisted_user.id)
    user = await get_current_user(db=db_session, access_token=token)

    assert user is not None
    assert user.id == persisted_user.id


@pytest.mark.asyncio
async def test_get_current_user_direct_user_none(db_session, create_jwt):
    """Directly calls get_current_user with a non-existent user ID to cover if user is None."""
    token = create_jwt(user_id=uuid.uuid4())

    with pytest.raises(CredentialsExceptionError):
        await get_current_user(db=db_session, access_token=token)


@pytest.mark.asyncio
async def test_get_current_workspace_user_direct_success(db_session, persisted_user):
    """Directly calls get_current_workspace_user to reliably cover return workspace_user."""
    workspace = Workspace(name="Direct WS", email="direct@test.com")
    db_session.add(workspace)
    await db_session.flush()

    workspace_user_link = WorkspaceUser(
        workspace_id=workspace.id,
        user_id=persisted_user.id,
        role="read_only",
        status=InvitationStatusEnum.ACTIVE,
        is_deleted=False,
    )
    db_session.add(workspace_user_link)
    await db_session.flush()

    result_link = await get_current_workspace_user(
        workspace_id=workspace.id,
        current_user=persisted_user,
        db=db_session,
    )

    assert result_link is not None
    assert result_link.id == workspace_user_link.id


@pytest.mark.asyncio
async def test_get_current_workspace_user_raises_when_missing(db_session, persisted_user):
    """Direct unit test ensuring WorkspaceUserNotFoundError is raised when tenancy record is missing."""
    with pytest.raises(WorkspaceUserNotFoundError):
        await get_current_workspace_user(
            workspace_id=uuid.uuid4(),
            current_user=persisted_user,
            db=db_session,
        )


@pytest.mark.asyncio
async def test_get_current_user_jwt_decode_error():
    """Forces a PyJWTError exception during decoding to ensure robust handling."""
    from src.erp.api.auth import dependencies

    db = AsyncMock()
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            dependencies.jwt,
            "decode",
            MagicMock(side_effect=jwt.PyJWTError()),
        )

        with pytest.raises(CredentialsExceptionError):
            await dependencies.get_current_user(
                db=db,
                access_token="definitely-invalid-token",
            )


# ============================================================================
# 2. FASTAPI INTEGRATION TEST CASES
# ============================================================================


async def test_get_current_user_happy_path_integration(test_client, create_jwt, persisted_user):
    """A valid access token for an existing user passes authentication via test client."""
    token = create_jwt(user_id=persisted_user.id)
    test_client.cookies.set("access_token", token)

    response = await test_client.get("/test-user")

    assert response.status_code == 200
    assert response.json() == {
        "id": str(persisted_user.id),
        "email": persisted_user.email,
    }


async def test_get_current_user_no_token(test_client):
    """Missing access_token cookie rejects the request."""
    response = await test_client.get("/test-user")
    assert response.status_code == 401


async def test_get_current_user_invalid_signature(test_client):
    """Tokens signed with an incorrect key fail authentication."""
    bad_token = jwt.encode(
        {"sub": str(uuid.uuid4()), "type": "access"},
        "WRONG_SECRET_KEY_WRONG_SECRET_KEY_WRONG_SECRET_KEY",
        algorithm=ALGORITHM,
    )
    test_client.cookies.set("access_token", bad_token)

    response = await test_client.get("/test-user")
    assert response.status_code == 401


async def test_get_current_user_malformed_token(test_client):
    """Non-JWT or malformed strings fail authentication."""
    test_client.cookies.set("access_token", "not-a-valid-jwt")
    response = await test_client.get("/test-user")
    assert response.status_code == 401


async def test_get_current_user_missing_sub_claim(test_client):
    """Tokens missing the 'sub' claim are rejected."""
    payload = {"type": "access", "exp": datetime.now(UTC) + timedelta(minutes=15)}
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    test_client.cookies.set("access_token", token)

    response = await test_client.get("/test-user")
    assert response.status_code == 401


async def test_get_current_user_missing_token_type(test_client, persisted_user):
    """Tokens missing the 'type' claim are rejected."""
    payload = {
        "sub": str(persisted_user.id),
        "exp": datetime.now(UTC) + timedelta(minutes=15),
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    test_client.cookies.set("access_token", token)

    response = await test_client.get("/test-user")
    assert response.status_code == 401


async def test_get_current_user_wrong_token_type(test_client, create_jwt, persisted_user):
    """Passing a 'refresh' token where an 'access' token is required fails."""
    refresh_token = create_jwt(user_id=persisted_user.id, token_type="refresh")
    test_client.cookies.set("access_token", refresh_token)

    response = await test_client.get("/test-user")
    assert response.status_code == 401


async def test_get_current_user_expired(test_client, create_jwt, persisted_user):
    """Expired access tokens fail verification."""
    expired_token = create_jwt(user_id=persisted_user.id, expires_delta=timedelta(minutes=-30))
    test_client.cookies.set("access_token", expired_token)

    response = await test_client.get("/test-user")
    assert response.status_code == 401


async def test_get_current_workspace_user_layer(test_client, create_jwt, db_session, persisted_user):
    """Verifies successful active workspace user tenancy retrieval via endpoint."""
    workspace = Workspace(name="Test Base WS", email="base_ws@test.com")
    db_session.add(workspace)
    await db_session.flush()

    workspace_user_link = WorkspaceUser(
        workspace_id=workspace.id,
        user_id=persisted_user.id,
        role="read_only",
        status=InvitationStatusEnum.ACTIVE,
        is_deleted=False,
    )
    db_session.add(workspace_user_link)
    await db_session.flush()

    token = create_jwt(user_id=persisted_user.id)
    test_client.cookies.set("access_token", token)

    response = await test_client.get(f"/test-active-user/{workspace.id}")

    assert response.status_code == 200
    assert response.json() == {
        "id": str(workspace_user_link.id),
        "user_id": str(persisted_user.id),
        "workspace_id": str(workspace.id),
        "role": "read_only",
        "status": InvitationStatusEnum.ACTIVE.value,
    }


async def test_get_current_workspace_user_not_found(test_client, create_jwt, persisted_user):
    """Access is denied if the user has no link to the target workspace."""
    token = create_jwt(user_id=persisted_user.id)
    test_client.cookies.set("access_token", token)

    response = await test_client.get(f"/test-active-user/{uuid.uuid4()}")
    assert response.status_code in (403, 404)


async def test_get_current_workspace_user_not_active(test_client, create_jwt, db_session, persisted_user):
    """Users with non-ACTIVE (e.g., PENDING) status are denied access."""
    workspace = Workspace(name="Pending WS", email="pending@test.com")
    db_session.add(workspace)
    await db_session.flush()

    workspace_user_link = WorkspaceUser(
        workspace_id=workspace.id,
        user_id=persisted_user.id,
        role="read_only",
        status=InvitationStatusEnum.PENDING,
        is_deleted=False,
    )
    db_session.add(workspace_user_link)
    await db_session.flush()

    token = create_jwt(user_id=persisted_user.id)
    test_client.cookies.set("access_token", token)

    response = await test_client.get(f"/test-active-user/{workspace.id}")
    assert response.status_code in (403, 404)


async def test_get_current_workspace_user_deleted(test_client, create_jwt, db_session, persisted_user):
    """Users whose workspace link has been soft-deleted are denied access."""
    workspace = Workspace(name="Deleted Link WS", email="deleted@test.com")
    db_session.add(workspace)
    await db_session.flush()

    workspace_user_link = WorkspaceUser(
        workspace_id=workspace.id,
        user_id=persisted_user.id,
        role="read_only",
        status=InvitationStatusEnum.ACTIVE,
        is_deleted=True,
    )
    db_session.add(workspace_user_link)
    await db_session.flush()

    token = create_jwt(user_id=persisted_user.id)
    test_client.cookies.set("access_token", token)

    response = await test_client.get(f"/test-active-user/{workspace.id}")
    assert response.status_code in (403, 404)
