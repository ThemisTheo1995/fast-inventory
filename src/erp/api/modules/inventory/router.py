from fastapi import APIRouter, Depends

from erp.api.auth.permissions import verify_workspace_access
from erp.api.pricing.dependencies import log_usage

from .views import router as inventory_router

router = APIRouter()
router.include_router(
    inventory_router,
    prefix="/{workspace_id}",
    tags=["Inventory"],
    dependencies=[Depends(verify_workspace_access), Depends(log_usage)],
)
