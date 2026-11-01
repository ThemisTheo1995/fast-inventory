import uuid
from dataclasses import dataclass

from erp.api.modules.bin.models import Bin


@dataclass
class BinCreatedEvent:
    workspace_id: uuid.UUID
    bin: Bin


@dataclass
class BinUpdatedEvent:
    workspace_id: uuid.UUID
    bin: Bin
