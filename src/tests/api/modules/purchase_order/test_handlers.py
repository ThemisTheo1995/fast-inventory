import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from erp.api.modules.purchase_order.events import (
    PurchaseOrderCreatedEvent,
    PurchaseOrderUpdatedEvent,
)
from erp.api.modules.purchase_order.handlers import (
    _handle_purchase_order_created,
    _handle_purchase_order_updated,
    register_purchase_order_handlers,
)


@pytest.mark.asyncio
@patch("erp.api.modules.purchase_order.handlers.process_purchase_order_search_index", new_callable=AsyncMock)
async def test_handle_purchase_order_created(mock_process_index: AsyncMock) -> None:
    purchase_order_id = uuid.uuid4()
    mock_event = MagicMock()
    mock_event.purchase_order.id = purchase_order_id

    await _handle_purchase_order_created(mock_event)

    mock_process_index.assert_awaited_once_with(purchase_order_id)


@pytest.mark.asyncio
@patch("erp.api.modules.purchase_order.handlers.process_purchase_order_search_index", new_callable=AsyncMock)
async def test_handle_purchase_order_updated(mock_process_index: AsyncMock) -> None:
    purchase_order_id = uuid.uuid4()
    mock_event = MagicMock()
    mock_event.purchase_order.id = purchase_order_id

    await _handle_purchase_order_updated(mock_event)

    mock_process_index.assert_awaited_once_with(purchase_order_id)


def test_register_purchase_order_handlers() -> None:
    mock_bus = MagicMock()

    register_purchase_order_handlers(mock_bus)

    assert mock_bus.subscribe.call_count == 2
    mock_bus.subscribe.assert_any_call(PurchaseOrderCreatedEvent, _handle_purchase_order_created)
    mock_bus.subscribe.assert_any_call(PurchaseOrderUpdatedEvent, _handle_purchase_order_updated)
