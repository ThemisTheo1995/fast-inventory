import uuid
from datetime import UTC, datetime

import pytest

from erp.api.modules.inventory.enums import StockMovementType

# ==============================================================================
# TEST DATA
# ==============================================================================


@pytest.fixture
def inventory_data():
    now = datetime.now(UTC)

    return {
        "id": uuid.uuid4(),
        "created_at": now,
        "updated_at": now,
        "workspace_id": uuid.uuid4(),
        "item_id": uuid.uuid4(),
        "bin_id": uuid.uuid4(),
        "quantity_on_hand": 25,
    }


@pytest.fixture
def stock_movement_data():
    now = datetime.now(UTC)

    return {
        "id": uuid.uuid4(),
        "workspace_id": uuid.uuid4(),
        "item_id": uuid.uuid4(),
        "bin_id": uuid.uuid4(),
        "quantity_change": 10,
        "reference_type": StockMovementType.MANUAL_ADJUSTMENT,
        "reference_id": uuid.uuid4(),
        "created_at": now,
        "updated_at": now,
        "notes": "Initial stock adjustment",
    }
