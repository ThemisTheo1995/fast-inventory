# Copyright 2026 Your Name
#
# Licensed under the Apache License, Version 2.0

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from src.erp import model_registry  # noqa: F401
from src.erp.api.router import api_router
from src.erp.core.exception_handlers import (
    custom_app_error_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from src.erp.core.exceptions import BaseAppError

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:  # noqa
    logger.info("Initializing FAST ERP API...")
    logger.info("Running database migrations via Alembic...")

    try:
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations completed successfully.")

    except Exception:
        logger.exception("Error during Alembic migrations")
        raise

    yield

    logger.info("Shutting down FAST ERP API...")


app = FastAPI(title="FAST ERP API", lifespan=lifespan)


# Register your custom app errors
app.add_exception_handler(BaseAppError, custom_app_error_handler)


# Override FastAPI's default Pydantic validation error handler
app.add_exception_handler(RequestValidationError, validation_exception_handler)


# Prevent raw 500 Stack Traces from leaking
app.add_exception_handler(Exception, unhandled_exception_handler)


# Define the origins that are allowed to talk to your API
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://vue-inventory-six.vercel.app",
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


handler = Mangum(app)
