class BaseAppError(Exception):
    """Base class for all custom application exceptions."""
    def __init__(self, detail: str, status_code: int = 400, code: str = "bad_request") -> None:
        self.detail = detail
        self.status_code = status_code
        self.code = code
