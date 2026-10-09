from datetime import date, datetime
from enum import Enum
from uuid import UUID


def serialize_value(val: object) -> object:
    """Ensure non-JSON serializable objects are converted to primitives."""
    if isinstance(val, (UUID, datetime, date)):
        return str(val)
    if isinstance(val, Enum):
        return val.value
    return val
