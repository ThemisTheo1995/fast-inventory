from fastapi import APIRouter, Depends

from erp.api.auth.permissions import verify_workspace_access

from .views import router as user_router

router = APIRouter()
router.include_router(
    user_router,
    prefix="/{workspace_id}",
    tags=["Workspace"],
    dependencies=[
        Depends(verify_workspace_access)
    ]
)
