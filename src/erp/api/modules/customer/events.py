import uuid
from dataclasses import dataclass

from erp.api.modules.customer.models import Customer


@dataclass
class CustomerCreatedEvent:
    workspace_id: uuid.UUID
    customer: Customer


@dataclass
class CustomerUpdatedEvent:
    workspace_id: uuid.UUID
    customer: Customer
