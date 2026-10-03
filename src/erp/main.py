# main.py
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from erp import model_registry  # noqa: F401
from erp.api.router import api_router
from erp.core.bootstrap import setup_application_events
from erp.core.exception_handlers import (
    custom_app_error_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from erp.core.exceptions import BaseAppError

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:  # noqa
    logger.info("Initialising FAST ERP API...")
    try:
        setup_application_events()
        logger.info("Application events initialized successfully.")
    except Exception:
        logger.exception("Fatal error during API startup initialization")
        raise

    yield
    logger.info("Shutting down FAST ERP API...")


app = FastAPI(title="FAST ERP API", lifespan=lifespan)

# Exception Handlers
app.add_exception_handler(BaseAppError, custom_app_error_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# Middleware
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://vue-inventory-six.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

handler = Mangum(app)
