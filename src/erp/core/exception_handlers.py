from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.erp.core.exceptions import BaseAppError


async def custom_app_error_handler(_request: Request, exc: BaseAppError) -> JSONResponse:
    """Passes your deliberate custom errors safely to the client."""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail, "code": exc.code})


async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """Intercepts system validation errors and sanitizes them so raw inputs aren't exposed."""

    sanitized_errors = []
    for error in exc.errors():
        field_name = error["loc"][-1] if error["loc"] else "unknown_field"
        sanitized_errors.append({"field": str(field_name), "message": "Invalid format or missing required data."})

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "detail": "The request payload or parameters are invalid.",
            "code": "validation_error",
            "errors": sanitized_errors,
        },
    )


async def unhandled_exception_handler(_request: Request, _exc: Exception) -> JSONResponse:
    """Catch-all for 500 errors so Python stack traces never leak."""

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An unexpected system error occurred. Please try again later.",
            "code": "internal_server_error",
        },
    )
