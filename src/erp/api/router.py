from fastapi import APIRouter

from erp.integrations.ebay.items import router as ebay_items_router
from erp.integrations.ebay.orders import router as ebay_orders_router
from erp.modules.orders import router as orders_router

api_router = APIRouter()

# Orders
api_router.include_router(orders_router)

# Ebay Orders
api_router.include_router(ebay_orders_router)
# Ebay Items
api_router.include_router(ebay_items_router)
