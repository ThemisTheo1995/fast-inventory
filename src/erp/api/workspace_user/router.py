from fastapi import APIRouter, Depends

from erp.api.auth.permissions import verify_workspace_access
from erp.api.pricing.dependencies import log_usage

from .views import router as workspace_user_router

router = APIRouter()
router.include_router(
    workspace_user_router,
    prefix="/{workspace_id}",
    tags=["WorkspaceUser"],
    dependencies=[Depends(verify_workspace_access), Depends(log_usage)],
)
