from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from erp import model_registry  # noqa: F401
from erp.api.router import api_router
from erp.core.exceptions import BaseAppError

app = FastAPI(title="ERP API")


# Global Exception
@app.exception_handler(BaseAppError)
async def custom_app_exception_handler(_request: Request, exc: BaseAppError) -> JSONResponse:
    """
    Catches all BaseAppErrors and returns a standardised JSON format.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.code,
            "detail": exc.detail
        }
    )

# Define the origins that are allowed to talk to your API
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    # Add your production domain here later
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
