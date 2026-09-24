from fastapi import APIRouter

from .views import router as email_router

router = APIRouter()
router.include_router(email_router, tags=["Email"])
