from fastapi import FastAPI

from src.erp.api.router import api_router

app = FastAPI(title="ERP API")

app.include_router(api_router)
