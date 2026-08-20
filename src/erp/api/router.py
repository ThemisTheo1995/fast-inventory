from fastapi import APIRouter

from src.erp.api.auth.router import router as auth_router
from src.erp.api.dashboard.router import router as dashboard_router
from src.erp.api.modules.customer.router import router as customer_router
from src.erp.api.modules.inventory.router import router as inventory_router
from src.erp.api.modules.item.router import router as item_router
from src.erp.api.modules.purchase_order.router import router as purchase_order_router
from src.erp.api.modules.sell_order.router import router as sell_order_router
from src.erp.api.modules.supplier.router import router as supplier_router
from src.erp.api.pricing.router import router as pricing_router
from src.erp.api.workspace.router import router as workspace_router
from src.erp.api.workspace_user.router import router as workspace_user_router

api_router = APIRouter()

# Auth
api_router.include_router(auth_router)

# Dashboard
api_router.include_router(dashboard_router)

# Modules.customer
api_router.include_router(customer_router)
# Modules.inventory
api_router.include_router(inventory_router)
# Modules.item
api_router.include_router(item_router)
# Modules.purchase_order
api_router.include_router(purchase_order_router)
# Modules.sell_order
api_router.include_router(sell_order_router)
# Modules.supplier
api_router.include_router(supplier_router)

# Pricing
api_router.include_router(pricing_router)

# Workspace
api_router.include_router(workspace_router)

# Workspace User
api_router.include_router(workspace_user_router)
