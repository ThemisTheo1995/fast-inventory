from fastapi import APIRouter

from .router import router as ebay_items_router

router = APIRouter()
router.include_router(
    ebay_items_router,
    prefix="/integrations/ebay/items",
    tags=["Ebay-Items"]
)
