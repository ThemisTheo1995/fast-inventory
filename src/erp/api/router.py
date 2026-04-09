from fastapi import APIRouter

from src.erp.modules.orders import router as orders_router

api_router = APIRouter()

# Orders
api_router.include_router(orders_router)
