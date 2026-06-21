from fastapi.testclient import TestClient
from pydantic import BaseModel

from erp.core.exceptions import BaseAppError
from erp.main import app

# ---------------------------------------------------------
# 1. Inject Temporary Routes into the Real App
# ---------------------------------------------------------
# We attach these to your real app so they get processed by
# your global exception handlers. We use a weird prefix
# (/_test_exceptions) so they never collide with real routes.


@app.get("/_test_exceptions/custom")
def _trigger_custom():
    raise BaseAppError(detail="You shall not pass", status_code=403, code="access_denied")


class DummyPayload(BaseModel):
    workspace_id: int


@app.post("/_test_exceptions/validation")
def _trigger_validation(payload: DummyPayload):
    return payload


@app.get("/_test_exceptions/unhandled")
def _trigger_unhandled():
    msg = "This is a secret database traceback that should never leak!"
    raise ValueError(msg)


# ---------------------------------------------------------
# 2. Test Cases using your existing `client` fixture
# ---------------------------------------------------------


def test_custom_app_error_handler(client):
    """Ensures our BaseAppError correctly maps detail, code, and status."""
    response = client.get("/_test_exceptions/custom")

    assert response.status_code == 403
    assert response.json() == {"detail": "You shall not pass", "code": "access_denied"}


def test_validation_exception_handler(client):
    """Ensures Pydantic errors are sanitized and raw inputs are hidden."""
    # Send a string where the schema strictly expects an integer
    bad_payload = {"workspace_id": "this_is_a_string"}
    response = client.post("/_test_exceptions/validation", json=bad_payload)

    assert response.status_code == 422

    data = response.json()
    assert data["detail"] == "The request payload or parameters are invalid."
    assert data["code"] == "validation_error"

    # Check that our sanitization stripped the raw input and exact error message
    assert len(data["errors"]) == 1
    assert data["errors"][0]["field"] == "workspace_id"
    assert data["errors"][0]["message"] == "Invalid format or missing required data."

    # Strictly ensure the attacker's raw input does not exist in the response
    assert "this_is_a_string" not in response.text


def test_unhandled_exception_handler():
    """Ensures random Python crashes return a clean 500 without leaking stack traces."""

    # Explicitly set raise_server_exceptions=False just for this test
    # so we can actually evaluate the JSON response of the 500 error.
    local_client = TestClient(app, raise_server_exceptions=False)

    response = local_client.get("/_test_exceptions/unhandled")

    assert response.status_code == 500
    assert response.json() == {
        "detail": "An unexpected system error occurred. Please try again later.",
        "code": "internal_server_error",
    }

    # Strictly ensure the internal traceback message did not leak
    assert "secret database traceback" not in response.text
