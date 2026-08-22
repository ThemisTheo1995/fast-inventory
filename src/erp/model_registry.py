# src/erp/model_registry.py

# Import your declarative base
from src.erp.api.base.models import Base

# Import every model explicitly to register them with Base.metadata

# Auth
from src.erp.api.auth.models import User
from src.erp.api.auth.models import UserSession

# Workspace
from src.erp.api.workspace.models import Workspace
from src.erp.api.workspace_user.models import WorkspaceUser

# WorkspaceUser Note
from src.erp.api.workspace_user_note.models import WorkspaceUserNote

# Pricing
from src.erp.api.pricing.models import PricingPlan, PricingSubscription, PricingUsage

# Modules.Customer
from src.erp.api.modules.customer.models import Customer

# Modules.Inventory
from src.erp.api.modules.inventory.models import Inventory, StockMovement

# Modules.Item
from src.erp.api.modules.item.models import Item

# Modules.Purchase Order
from src.erp.api.modules.purchase_order.models import PurchaseOrder, PurchaseOrderLine

# Modules.Sell Order
from src.erp.api.modules.sell_order.models import SellOrder, SellOrderLine

# Modules.Supplier
from src.erp.api.modules.supplier.models import Supplier

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
]

metadata = Base.metadata
