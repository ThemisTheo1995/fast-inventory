class EmailServiceError(Exception):
    """Base exception for email service domain errors."""

    pass


class EmailSendError(EmailServiceError):
    """Raised when sending an email fails."""

    def __init__(self, message: str, original_error: Exception | None = None) -> None:
        super().__init__(message)
        self.original_error = original_error


class EmailConfigurationError(EmailServiceError):
    """Raised when provider settings are invalid or missing."""

    pass
