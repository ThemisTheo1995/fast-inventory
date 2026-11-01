import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from erp.api.modules.bin.events import (
    BinCreatedEvent,
    BinUpdatedEvent,
)
from erp.api.modules.bin.handlers import (
    _handle_bin_created,
    _handle_bin_updated,
    register_bin_handlers,
)


@pytest.fixture
def bin_event():
    bin_obj = MagicMock()
    bin_obj.id = uuid.uuid4()

    return BinCreatedEvent(
        workspace_id=uuid.uuid4(),
        bin=bin_obj,
    )


# ==============================================================================
# BIN CREATED HANDLER
# ==============================================================================


@pytest.mark.asyncio
async def test_handle_bin_created(bin_event):
    with patch(
        "erp.api.modules.bin.handlers.process_bin_search_index",
        new_callable=AsyncMock,
    ) as mock_process:
        await _handle_bin_created(bin_event)

    mock_process.assert_awaited_once_with(bin_event.bin.id)


@pytest.mark.asyncio
async def test_handle_bin_created_propagates_error(bin_event):
    with (
        patch(
            "erp.api.modules.bin.handlers.process_bin_search_index",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Embedding failed"),
        ),
        pytest.raises(RuntimeError, match="Embedding failed"),
    ):
        await _handle_bin_created(bin_event)


# ==============================================================================
# BIN UPDATED HANDLER
# ==============================================================================


@pytest.mark.asyncio
async def test_handle_bin_updated(bin_event):
    event = BinUpdatedEvent(
        workspace_id=bin_event.workspace_id,
        bin=bin_event.bin,
    )

    with patch(
        "erp.api.modules.bin.handlers.process_bin_search_index",
        new_callable=AsyncMock,
    ) as mock_process:
        await _handle_bin_updated(event)

    mock_process.assert_awaited_once_with(event.bin.id)


@pytest.mark.asyncio
async def test_handle_bin_updated_propagates_error(bin_event):
    event = BinUpdatedEvent(
        workspace_id=bin_event.workspace_id,
        bin=bin_event.bin,
    )

    with (
        patch(
            "erp.api.modules.bin.handlers.process_bin_search_index",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Embedding failed"),
        ),
        pytest.raises(RuntimeError, match="Embedding failed"),
    ):
        await _handle_bin_updated(event)


# ==============================================================================
# HANDLER REGISTRATION
# ==============================================================================


def test_register_bin_handlers():
    bus = MagicMock()

    register_bin_handlers(bus)

    assert bus.subscribe.call_count == 2

    subscriptions = {call.args[0]: call.args[1] for call in bus.subscribe.call_args_list}

    assert subscriptions[BinCreatedEvent] is _handle_bin_created
    assert subscriptions[BinUpdatedEvent] is _handle_bin_updated


def test_register_bin_handlers_subscribes_correct_event_types():
    bus = MagicMock()

    register_bin_handlers(bus)

    subscribed_types = [call.args[0] for call in bus.subscribe.call_args_list]

    assert subscribed_types == [
        BinCreatedEvent,
        BinUpdatedEvent,
    ]
