# src/erp/model_registry.py

# Import your declarative base
from erp.api.base.models import Base

# Import every model explicitly to register them with Base.metadata

# AUTH
from erp.api.auth.models import User
from erp.api.auth.models import UserSession

# WORKSPACE
from erp.api.workspace.models import Workspace
from erp.api.workspace.models import WorkspaceUser

# INTEGRATION
from erp.integrations.models import Integration

# EBAY
from erp.integrations.ebay.items.models import EbayItem

__all__ = [
    "Base",
    "User",
    "UserSession",
    "Workspace",
    "WorkspaceUser",
    "Integration",
    "EbayItem"
]

metadata = Base.metadata
