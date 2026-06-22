import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.erp.api.auth.dependencies import get_current_active_user, get_current_user
from src.erp.api.auth.models import User
from src.erp.api.auth.utils import get_password_hash
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


@app.get("/test-active-user")
def mock_active_user_endpoint(current_active_user: Annotated[User, Depends(get_current_active_user)]):
    return {"id": str(current_active_user.id), "email": current_active_user.email}


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

    def _encode(user_id: str, token_type: str = "access", expires_delta: timedelta | None = None):
        expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=15))
        payload = {"sub": str(user_id), "type": token_type, "exp": expire}
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
    A valid access token belonging to an existing user must pass
    authentication and return the user record.
    """
    token = create_jwt(user_id=persisted_user.id)

    response = test_client.get("/test-user", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {"id": str(persisted_user.id), "email": persisted_user.email}


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

    response = test_client.get("/test-user", headers={"Authorization": f"Bearer {bad_token}"})
    assert response.status_code == 401


def test_get_current_user_missing_sub_claim(test_client):
    """
    A token missing its subject ('sub') claim cannot identify a user
    and must trigger an exception.
    """
    payload = {"type": "access", "exp": datetime.now(UTC) + timedelta(minutes=15)}
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    response = test_client.get("/test-user", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_get_current_user_wrong_token_type(test_client, create_jwt, persisted_user):
    """
    Passing a 'refresh' type token into an endpoint requiring an
    'access' token must fail verification.
    """
    refresh_token = create_jwt(user_id=persisted_user.id, token_type="refresh")

    response = test_client.get("/test-user", headers={"Authorization": f"Bearer {refresh_token}"})
    assert response.status_code == 401


def test_get_current_user_expired(test_client, create_jwt, persisted_user):
    """
    An expired access token must fail cleanly.
    """
    expired_token = create_jwt(user_id=persisted_user.id, expires_delta=timedelta(minutes=-30))

    response = test_client.get("/test-user", headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == 401


def test_get_current_user_not_found_in_db(test_client, create_jwt):
    """
    If the token signature is structurally correct but the subject user ID
    no longer exists in the database, it must deny access.
    """
    token = create_jwt(user_id=str(uuid.uuid4()))

    response = test_client.get("/test-user", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_get_current_active_user_layer(test_client, create_jwt, persisted_user):
    """
    Verifies that the secondary dependency wrapper correctly forwards
    the active authenticated user payload.
    """
    token = create_jwt(user_id=persisted_user.id)

    response = test_client.get("/test-active-user", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {"id": str(persisted_user.id), "email": persisted_user.email}
