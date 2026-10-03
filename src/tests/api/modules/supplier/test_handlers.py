from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from erp.api.modules.supplier.events import (
    SupplierCreatedEvent,
    SupplierUpdatedEvent,
)
from erp.api.modules.supplier.handlers import (
    _handle_supplier_created,
    _handle_supplier_updated,
    register_supplier_handlers,
)


@pytest.mark.asyncio
async def test_handle_supplier_created(mock_process_supplier_search_index):
    supplier_id = uuid4()

    supplier = MagicMock()
    supplier.id = supplier_id

    event = SupplierCreatedEvent(
        workspace_id=uuid4(),
        supplier=supplier,
    )

    await _handle_supplier_created(event)

    mock_process_supplier_search_index.assert_awaited_once_with(supplier_id)


@pytest.mark.asyncio
async def test_handle_supplier_updated(mock_process_supplier_search_index):
    supplier_id = uuid4()

    supplier = MagicMock()
    supplier.id = supplier_id

    event = SupplierUpdatedEvent(
        workspace_id=uuid4(),
        supplier=supplier,
    )

    await _handle_supplier_updated(event)

    mock_process_supplier_search_index.assert_awaited_once_with(supplier_id)


def test_register_supplier_handlers():
    bus = MagicMock()

    register_supplier_handlers(bus)

    assert bus.subscribe.call_count == 2

    bus.subscribe.assert_any_call(
        SupplierCreatedEvent,
        _handle_supplier_created,
    )

    bus.subscribe.assert_any_call(
        SupplierUpdatedEvent,
        _handle_supplier_updated,
    )
