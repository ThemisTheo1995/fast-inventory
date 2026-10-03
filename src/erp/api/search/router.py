from fastapi import APIRouter, Depends

from erp.api.auth.permissions import verify_workspace_access
from erp.api.pricing.dependencies import log_usage

from .views import router as search_router

router = APIRouter()
router.include_router(
    search_router,
    prefix="/{workspace_id}",
    tags=["Global-Search"],
    dependencies=[Depends(verify_workspace_access), Depends(log_usage)],
)
