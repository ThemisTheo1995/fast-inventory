from fastapi import APIRouter, Depends
from src.erp.api.auth.permissions import verify_workspace_access
from src.erp.api.pricing.dependencies import log_usage

from .views import router as workspace_user_note_router

router = APIRouter()
router.include_router(
    workspace_user_note_router,
    prefix="/{workspace_id}",
    tags=["WorkspaceUser-Note"],
    dependencies=[Depends(verify_workspace_access), Depends(log_usage)],
)
