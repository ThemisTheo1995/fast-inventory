from fastapi import APIRouter, Depends

from erp.api.auth.permissions import verify_workspace_access
from erp.api.pricing.dependencies import log_usage

from .views import router as item_router

router = APIRouter()
router.include_router(
    item_router,
    prefix="/{workspace_id}",
    tags=["Purchase-Order"],
    dependencies=[Depends(verify_workspace_access), Depends(log_usage)],
)
