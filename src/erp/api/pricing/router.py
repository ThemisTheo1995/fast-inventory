from fastapi import APIRouter, Depends

from erp.api.auth.permissions import verify_workspace_access

from .views import router as pricing_router

router = APIRouter()
router.include_router(
    pricing_router,
    tags=["Pricing"],
    dependencies=[
        Depends(verify_workspace_access),
    ],
)
