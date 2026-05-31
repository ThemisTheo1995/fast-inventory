from fastapi import APIRouter, Depends

from erp.api.auth.dependencies import get_current_active_user, get_current_workspace

from .views import router as user_router

router = APIRouter()
router.include_router(
    user_router,
    prefix="/{workspace_id}/members",
    tags=["Workspace-Members"],
    dependencies=[
        Depends(get_current_active_user),
        Depends(get_current_workspace)
    ]
)
