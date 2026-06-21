from fastapi import status

from erp.core.exceptions import BaseAppError


class TokenError(Exception):
    """Base class for token-related exceptions."""
    pass


class TokenExpiredError(TokenError):
    """Raised when a token has expired."""
    pass


class TokenInvalidError(TokenError):
    """Raised when a token is invalid."""
    pass


class UserExistsExceptionError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists."
        )


class OnboardingFailedExceptionError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Onboarding failed, please contact support."
        )


class CredentialsExceptionError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials."
        )


class InsufficientPermissionsError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have the required permissions to perform this action in this workspace."
        )


class InvitationNotFoundExceptionError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No pending invitation found for this email address.",
        )


class AccountAlreadyOnboardedExceptionError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account has already been fully onboarded. Login instead.",
        )
