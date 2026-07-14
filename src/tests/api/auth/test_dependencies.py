import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.erp.api.auth.dependencies import get_current_user, get_current_workspace_user
from src.erp.api.auth.models import User
from src.erp.api.auth.utils import get_password_hash
from src.erp.api.workspace.models import Workspace
from src.erp.api.workspace_user.enums import InvitationStatusEnum
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

# Register the base handler exactly how your main.py does it!
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


@pytest.fixture
def test_client(db_session):
    """
    Creates a FastAPI TestClient and overrides the global 'get_db'
    dependency to use your real, isolated 'db_session' fixture.
    """
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def create_jwt():
    """Helper tool to encode valid/invalid testing tokens."""

    def _encode(
        user_id: str,
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


@pytest.fixture
def persisted_user(db_session):
    """Creates and flushes a baseline user into the test database."""
    user = User(
        id=str(uuid.uuid4()),
        email="dep_test@example.com",
        first_name="Dep",
        last_name="Tester",
        hashed_password=get_password_hash("secure_pass"),
    )
    db_session.add(user)
    db_session.flush()
    return user


# ============================================================================
# DEPENDENCY TEST CASES
# ============================================================================


def test_get_current_user_happy_path(test_client, create_jwt, persisted_user):
    """
    A valid access token stored in the access_token cookie belonging to an existing
    user must pass authentication and return the user record.
    """
    token = create_jwt(user_id=persisted_user.id)

    test_client.cookies.set("access_token", token)

    response = test_client.get("/test-user")

    assert response.status_code == 200
    assert response.json() == {
        "id": str(persisted_user.id),
        "email": persisted_user.email,
    }


def test_get_current_user_invalid_signature(test_client):
    """
    Tokens tampered with or signed with an incorrect key must
    fail authentication instantly.
    """
    bad_token = jwt.encode(
        {"sub": str(uuid.uuid4()), "type": "access"},
        "WRONG_SECRET_KEY_WRONG_SECRET_KEY_WRONG_SECRET_KEY",
        algorithm=ALGORITHM,
    )

    test_client.cookies.set("access_token", bad_token)

    response = test_client.get("/test-user")
    assert response.status_code == 401


def test_get_current_user_missing_sub_claim(test_client):
    """
    A token missing its subject ('sub') claim cannot identify a user
    and must trigger an exception.
    """
    payload = {"type": "access", "exp": datetime.now(UTC) + timedelta(minutes=15)}
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    test_client.cookies.set("access_token", token)

    response = test_client.get("/test-user")
    assert response.status_code == 401


def test_get_current_user_wrong_token_type(test_client, create_jwt, persisted_user):
    """
    Passing a 'refresh' type token into an endpoint requiring an
    'access' token must fail verification.
    """
    refresh_token = create_jwt(user_id=persisted_user.id, token_type="refresh")

    test_client.cookies.set("access_token", refresh_token)

    response = test_client.get("/test-user")
    assert response.status_code == 401


def test_get_current_user_expired(test_client, create_jwt, persisted_user):
    """
    An expired access token must fail cleanly.
    """
    expired_token = create_jwt(user_id=persisted_user.id, expires_delta=timedelta(minutes=-30))

    test_client.cookies.set("access_token", expired_token)

    response = test_client.get("/test-user")
    assert response.status_code == 401


def test_get_current_user_not_found_in_db(test_client, create_jwt):
    """
    If the token signature is structurally correct but the subject user ID
    no longer exists in the database, it must deny access.
    """
    token = create_jwt(user_id=str(uuid.uuid4()))

    test_client.cookies.set("access_token", token)

    response = test_client.get("/test-user")
    assert response.status_code == 401


def test_get_current_workspace_user_layer(test_client, create_jwt, db_session, persisted_user):
    """
    Verifies that the secondary dependency wrapper correctly fetches
    the active workspace tenancy link when valid credentials and parameters match.
    """
    workspace = Workspace(
        name="Test Base WS",
        email="base_ws@test.com",
    )
    db_session.add(workspace)
    db_session.flush()

    workspace_user_link = WorkspaceUser(
        workspace_id=workspace.id,
        user_id=persisted_user.id,
        role="read_only",
        status=InvitationStatusEnum.ACTIVE.value,
        is_deleted=False,
    )
    db_session.add(workspace_user_link)
    db_session.flush()

    token = create_jwt(user_id=persisted_user.id)

    # Cookie-based authentication
    test_client.cookies.set("access_token", token)

    response = test_client.get(f"/test-active-user/{workspace.id}")

    assert response.status_code == 200
    assert response.json() == {
        "id": str(workspace_user_link.id),
        "user_id": str(persisted_user.id),
        "workspace_id": str(workspace.id),
        "role": "read_only",
        "status": InvitationStatusEnum.ACTIVE.value,
    }
