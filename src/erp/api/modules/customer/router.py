from fastapi import APIRouter, Depends

from src.erp.api.auth.permissions import verify_workspace_access
from src.erp.api.pricing.dependencies import log_usage

from .views import router as customer_router

router = APIRouter()
router.include_router(
    customer_router,
    prefix="/{workspace_id}",
    tags=["Customer"],
    dependencies=[Depends(verify_workspace_access), Depends(log_usage)],
)
