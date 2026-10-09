from fastapi import APIRouter

from .views import router as pricing_router

router = APIRouter()
router.include_router(
    pricing_router,
    tags=["Pricing"],
)
