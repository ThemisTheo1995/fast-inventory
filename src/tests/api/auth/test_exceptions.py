from fastapi import status

from erp.api.auth.exceptions import (
    AccountAlreadyOnboardedExceptionError,
    CredentialsExceptionError,
    InsufficientPermissionsError,
    InvitationNotFoundExceptionError,
    OnboardingFailedExceptionError,
    PricingPlanDoesNotExistError,
    TokenError,
    TokenExpiredError,
    TokenInvalidError,
    UserExistsExceptionError,
)
from erp.core.exceptions import BaseAppError

# ==============================================================================
# STANDARD EXCEPTION TESTS (Token Hierarchy)
# ==============================================================================


def test_token_error_hierarchy():
    """Verifies that the token exceptions correctly inherit from standard Exception."""
    base_err = TokenError("Base error")
    expired_err = TokenExpiredError("Expired")
    invalid_err = TokenInvalidError("Invalid")

    assert isinstance(base_err, Exception)

    assert isinstance(expired_err, TokenError)
    assert isinstance(expired_err, Exception)

    assert isinstance(invalid_err, TokenError)
    assert isinstance(invalid_err, Exception)


# ==============================================================================
# BASE APP ERROR TESTS (HTTP Status & Messages)
# ==============================================================================


def test_user_exists_exception():
    """Verifies UserExistsExceptionError initializes with 400 status and correct detail."""
    err = UserExistsExceptionError()

    assert isinstance(err, BaseAppError)
    assert err.status_code == status.HTTP_400_BAD_REQUEST
    assert err.detail == "A user with this email already exists."


def test_onboarding_failed_exception():
    """Verifies OnboardingFailedExceptionError initializes with 400 status and correct detail."""
    err = OnboardingFailedExceptionError()

    assert isinstance(err, BaseAppError)
    assert err.status_code == status.HTTP_400_BAD_REQUEST
    assert err.detail == "Onboarding failed, please contact support."


def test_credentials_exception():
    """Verifies CredentialsExceptionError initializes with 401 status and correct detail."""
    err = CredentialsExceptionError()

    assert isinstance(err, BaseAppError)
    assert err.status_code == status.HTTP_401_UNAUTHORIZED
    assert err.detail == "Could not validate credentials."


def test_insufficient_permissions_error():
    """Verifies InsufficientPermissionsError initializes with 403 status and correct detail."""
    err = InsufficientPermissionsError()

    assert isinstance(err, BaseAppError)
    assert err.status_code == status.HTTP_403_FORBIDDEN
    assert err.detail == "You do not have the required permissions to perform this action in this workspace."


def test_invitation_not_found_exception():
    """Verifies InvitationNotFoundExceptionError initializes with 404 status and correct detail."""
    err = InvitationNotFoundExceptionError()

    assert isinstance(err, BaseAppError)
    assert err.status_code == status.HTTP_404_NOT_FOUND
    assert err.detail == "No pending invitation found for this email address."


def test_account_already_onboarded_exception():
    """Verifies AccountAlreadyOnboardedExceptionError initializes with 400 status and correct detail."""
    err = AccountAlreadyOnboardedExceptionError()

    assert isinstance(err, BaseAppError)
    assert err.status_code == status.HTTP_400_BAD_REQUEST
    assert err.detail == "This account has already been fully onboarded. Login instead."


def test_pricing_plan_does_not_exist_error():
    """Verifies PricingPlanDoesNotExistError initializes with 404 status and correct detail."""
    err = PricingPlanDoesNotExistError()

    assert isinstance(err, BaseAppError)
    assert err.status_code == status.HTTP_404_NOT_FOUND
    assert err.detail == "Pricing plan does not exist."
