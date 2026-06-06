from fastapi import APIRouter

from erp.api.auth import router as auth_router
from erp.api.workspace import router as workspace_router
from erp.integrations.ebay.items import router as ebay_items_router

api_router = APIRouter()

# Auth
api_router.include_router(auth_router)

# Workspace
api_router.include_router(workspace_router)

# Ebay Items
api_router.include_router(ebay_items_router)
