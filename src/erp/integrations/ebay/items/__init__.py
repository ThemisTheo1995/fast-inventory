from fastapi import APIRouter, Depends

from erp.api.auth.dependencies import get_current_active_user, get_current_workspace

from .views import router as ebay_items_router

router = APIRouter()

router.include_router(
    ebay_items_router,
    prefix="/{workspace_id}/integrations/ebay/items",
    tags=["Ebay-Items"],
    dependencies=[
        Depends(get_current_active_user),
        Depends(get_current_workspace)
    ]
)
