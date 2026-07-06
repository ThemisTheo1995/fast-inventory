# src/erp/model_registry.py

# Import your declarative base
from src.erp.api.base.models import Base

# Import every model explicitly to register them with Base.metadata

# AUTH
from src.erp.api.auth.models import User
from src.erp.api.auth.models import UserSession

# WORKSPACE
from src.erp.api.workspace.models import Workspace
from src.erp.api.workspace_user.models import WorkspaceUser

# PRICING
from src.erp.api.pricing.models import PricingPlan, PricingSubscription, PricingUsage

# MODULES
# Customer
from src.erp.api.modules.customer.models import Customer

# Inventory
from src.erp.api.modules.inventory.models import Inventory, StockMovement

# Item
from src.erp.api.modules.item.models import Item

# Purchase Order
from src.erp.api.modules.purchase_order.models import PurchaseOrder, PurchaseOrderLine

# Sell Order
from src.erp.api.modules.sell_order.models import SellOrder, SellOrderLine

# Supplier
from src.erp.api.modules.supplier.models import Supplier

# INTEGRATION
from src.erp.integrations.models import Integration

# EBAY
from src.erp.integrations.ebay.items.models import EbayItem

__all__ = [
    "Base",
    "User",
    "UserSession",
    "Workspace",
    "WorkspaceUser",
    "PricingPlan",
    "PricingSubscription",
    "PricingUsage",
    "Customer",
    "Inventory",
    "StockMovement",
    "Item",
    "PurchaseOrder",
    "PurchaseOrderLine",
    "SellOrder",
    "SellOrderLine",
    "Supplier",
    "Integration",
    "EbayItem",
]

metadata = Base.metadata
