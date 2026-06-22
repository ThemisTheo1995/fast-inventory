# src/erp/model_registry.py

# Import your declarative base
from src.erp.api.base.models import Base

# Import every model explicitly to register them with Base.metadata

# AUTH
from src.erp.api.auth.models import User
from src.erp.api.auth.models import UserSession

# WORKSPACE
from src.erp.api.workspace.models import Workspace
from src.erp.api.workspace.models import WorkspaceUser

# INTEGRATION
from src.erp.integrations.models import Integration

# EBAY
from src.erp.integrations.ebay.items.models import EbayItem

__all__ = ["Base", "User", "UserSession", "Workspace", "WorkspaceUser", "Integration", "EbayItem"]

metadata = Base.metadata
