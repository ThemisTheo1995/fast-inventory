from fastapi import APIRouter

from .router import router as ebay_orders_router

router = APIRouter()
router.include_router(
    ebay_orders_router,
    prefix="/integrations/ebay/orders",
    tags=["Ebay-Orders"]
)
