from fastapi import APIRouter

from src.erp.api.auth.router import router as auth_router
from src.erp.api.modules.customer.router import router as customer_router
from src.erp.api.pricing.router import router as pricing_router
from src.erp.api.workspace.router import router as workspace_router
from src.erp.api.workspace_user.router import router as workspace_user_router
from src.erp.integrations.ebay.items.router import router as ebay_items_router

api_router = APIRouter()

# Auth
api_router.include_router(auth_router)

# Modules.customer
api_router.include_router(customer_router)

# Pricing
api_router.include_router(pricing_router)

# Workspace
api_router.include_router(workspace_router)

# Workspace User
api_router.include_router(workspace_user_router)

# Ebay Items
api_router.include_router(ebay_items_router)
