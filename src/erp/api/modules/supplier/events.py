import uuid
from dataclasses import dataclass

from src.erp.api.modules.supplier.models import Supplier


@dataclass
class SupplierCreatedEvent:
    workspace_id: uuid.UUID
    supplier: Supplier


@dataclass
class SupplierUpdatedEvent:
    workspace_id: uuid.UUID
    supplier: Supplier
