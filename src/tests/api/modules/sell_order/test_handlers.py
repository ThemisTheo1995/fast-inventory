import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from erp.api.modules.sell_order.events import (
    SellOrderCreatedEvent,
    SellOrderUpdatedEvent,
)
from erp.api.modules.sell_order.handlers import (
    _handle_sell_order_created,
    _handle_sell_order_updated,
    register_sell_order_handlers,
)


@pytest.mark.asyncio
@patch("erp.api.modules.sell_order.handlers.process_sell_order_search_index", new_callable=AsyncMock)
async def test_handle_sell_order_created(mock_process_index: AsyncMock):
    sell_order_id = uuid.uuid4()
    sell_order = MagicMock()
    sell_order.id = sell_order_id

    event = SellOrderCreatedEvent(
        workspace_id=uuid.uuid4(),
        sell_order=sell_order,
    )

    await _handle_sell_order_created(event)

    mock_process_index.assert_awaited_once_with(sell_order_id)


@pytest.mark.asyncio
@patch("erp.api.modules.sell_order.handlers.process_sell_order_search_index", new_callable=AsyncMock)
async def test_handle_sell_order_updated(mock_process_index: AsyncMock):
    sell_order_id = uuid.uuid4()
    sell_order = MagicMock()
    sell_order.id = sell_order_id

    event = SellOrderUpdatedEvent(
        workspace_id=uuid.uuid4(),
        sell_order=sell_order,
    )

    await _handle_sell_order_updated(event)

    mock_process_index.assert_awaited_once_with(sell_order_id)


def test_register_sell_order_handlers():
    mock_bus = MagicMock()

    register_sell_order_handlers(mock_bus)

    assert mock_bus.subscribe.call_count == 2
    mock_bus.subscribe.assert_any_call(SellOrderCreatedEvent, _handle_sell_order_created)
    mock_bus.subscribe.assert_any_call(SellOrderUpdatedEvent, _handle_sell_order_updated)
