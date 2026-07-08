from fastapi import APIRouter, Depends

from src.erp.api.auth.permissions import verify_workspace_access
from src.erp.api.pricing.dependencies import log_usage

from .views import router as ebay_items_router

router = APIRouter()

router.include_router(
    ebay_items_router,
    prefix="/{workspace_id}/integrations/ebay/items",
    tags=["Ebay-Items"],
    dependencies=[Depends(verify_workspace_access), Depends(log_usage)],
)
