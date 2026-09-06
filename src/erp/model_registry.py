# src/erp/model_registry.py

# Import your declarative base
from erp.api.base.models import Base

# Import every model explicitly to register them with Base.metadata

# Auth
from erp.api.auth.models import User
from erp.api.auth.models import UserSession

# Workspace
from erp.api.workspace.models import Workspace
from erp.api.workspace_user.models import WorkspaceUser

# WorkspaceUser Note
from erp.api.workspace_user_note.models import WorkspaceUserNote

# Pricing
from erp.api.pricing.models import PricingPlan, PricingSubscription, PricingUsage

# Modules.Customer
from erp.api.modules.customer.models import Customer

# Modules.Inventory
from erp.api.modules.inventory.models import Inventory, StockMovement

# Modules.Item
from erp.api.modules.item.models import Item

# Modules.Purchase Order
from erp.api.modules.purchase_order.models import PurchaseOrder, PurchaseOrderLine

# Modules.Sell Order
from erp.api.modules.sell_order.models import SellOrder, SellOrderLine

# Modules.Supplier
from erp.api.modules.supplier.models import Supplier

# Search
from erp.api.search.models import GlobalSearchIndex

__all__ = [
    "Base",
    "User",
    "UserSession",
    "Workspace",
    "WorkspaceUser",
    "WorkspaceUserNote",
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
    "GlobalSearchIndex",
]

metadata = Base.metadata
