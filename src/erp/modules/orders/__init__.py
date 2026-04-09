from fastapi import APIRouter

from .router import router as orders_router

router = APIRouter()
router.include_router(orders_router, prefix="/orders", tags=["Orders"])
