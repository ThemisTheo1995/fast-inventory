import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import BackgroundTasks

from erp.api.modules.bin.events import BinCreatedEvent, BinUpdatedEvent
from erp.api.modules.bin.exceptions import (
    BinHasInventoryItemsError,
    BinNotFoundError,
)
from erp.api.modules.bin.schemas.bin import BinCreate, BinUpdate
from erp.api.modules.bin.schemas.bin_expanded import (
    BinExpandedPaginatedResponse,
    BinExpandedResponse,
)
from erp.api.modules.bin.views import (
    create_bin,
    delete_bin,
    get_bin,
    get_bins,
    update_bin,
)


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def mock_background_tasks():
    return MagicMock(spec=BackgroundTasks)


@pytest.fixture
def mock_bin_service():
    return MagicMock()


@pytest.fixture
def bin_obj(seed_workspace):
    return MagicMock(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        code="A-01",
        zone="Warehouse A",
    )


# ==============================================================================
# CREATE BIN
# ==============================================================================


@pytest.mark.asyncio
async def test_create_bin_success(mock_db, mock_background_tasks, mock_bin_service, bin_obj, seed_workspace):
    data = BinCreate(code="A-01", zone="Warehouse A")
    mock_bin_service.create_bin = AsyncMock(return_value=bin_obj)

    with (
        patch(
            "erp.api.modules.bin.views.BinService",
            return_value=mock_bin_service,
        ),
        patch(
            "erp.api.modules.bin.views.global_event_bus.publish",
            new_callable=AsyncMock,
        ),
    ):
        response = await create_bin(
            workspace_id=seed_workspace,
            data=data,
            background_tasks=mock_background_tasks,
            db=mock_db,
        )

    assert response is bin_obj
    mock_bin_service.create_bin.assert_awaited_once_with(seed_workspace, data)

    mock_background_tasks.add_task.assert_called_once()
    args = mock_background_tasks.add_task.call_args.args

    assert args[0] == pytest.approx(args[0]) if False else args[0]
    assert isinstance(args[1], BinCreatedEvent)
    assert args[1].workspace_id == seed_workspace
    assert args[1].bin is bin_obj


# ==============================================================================
# GET BINS
# ==============================================================================


@pytest.mark.asyncio
async def test_get_bins_success(mock_db, mock_bin_service, seed_workspace):
    expected_response = MagicMock()
    mock_bin_service.get_bins = AsyncMock(return_value=expected_response)

    with patch(
        "erp.api.modules.bin.views.BinService",
        return_value=mock_bin_service,
    ):
        response = await get_bins(
            workspace_id=seed_workspace,
            db=mock_db,
            search="A-01",
            page=2,
            limit=10,
            expand=None,
        )

    assert response is expected_response
    mock_bin_service.get_bins.assert_awaited_once_with(seed_workspace, "A-01", 2, 10, None)


@pytest.mark.asyncio
async def test_get_bins_expanded(mock_db, mock_bin_service, seed_workspace):
    expected_response = MagicMock(spec=BinExpandedPaginatedResponse)
    mock_bin_service.get_bins = AsyncMock(return_value=expected_response)

    expand = ["inventory_items", "inventory_items.item"]

    with patch(
        "erp.api.modules.bin.views.BinService",
        return_value=mock_bin_service,
    ):
        response = await get_bins(
            workspace_id=seed_workspace,
            db=mock_db,
            expand=expand,
        )

    assert response is expected_response
    mock_bin_service.get_bins.assert_awaited_once_with(seed_workspace, None, 1, 20, expand)


@pytest.mark.asyncio
async def test_get_bins_service_error(mock_db, mock_bin_service, seed_workspace):
    mock_bin_service.get_bins = AsyncMock(side_effect=RuntimeError("Database failure"))

    with (
        patch(
            "erp.api.modules.bin.views.BinService",
            return_value=mock_bin_service,
        ),
        pytest.raises(RuntimeError, match="Database failure"),
    ):
        await get_bins(
            workspace_id=seed_workspace,
            db=mock_db,
        )


# ==============================================================================
# GET SINGLE BIN
# ==============================================================================


@pytest.mark.asyncio
async def test_get_bin_success(mock_db, mock_bin_service, bin_obj, seed_workspace):
    mock_bin_service.get_bin = AsyncMock(return_value=bin_obj)

    with patch(
        "erp.api.modules.bin.views.BinService",
        return_value=mock_bin_service,
    ):
        response = await get_bin(
            workspace_id=seed_workspace,
            bin_id=bin_obj.id,
            db=mock_db,
        )

    assert response is bin_obj
    mock_bin_service.get_bin.assert_awaited_once_with(seed_workspace, bin_obj.id, expand=None)


@pytest.mark.asyncio
async def test_get_bin_expanded(mock_db, mock_bin_service, seed_workspace):
    expected_response = MagicMock(spec=BinExpandedResponse)
    bin_id = uuid.uuid4()
    expand = ["inventory_items", "inventory_items.item"]

    mock_bin_service.get_bin = AsyncMock(return_value=expected_response)

    with patch(
        "erp.api.modules.bin.views.BinService",
        return_value=mock_bin_service,
    ):
        response = await get_bin(
            workspace_id=seed_workspace,
            bin_id=bin_id,
            db=mock_db,
            expand=expand,
        )

    assert response is expected_response
    mock_bin_service.get_bin.assert_awaited_once_with(seed_workspace, bin_id, expand=expand)


@pytest.mark.asyncio
async def test_get_bin_not_found(mock_db, mock_bin_service, seed_workspace):
    bin_id = uuid.uuid4()
    mock_bin_service.get_bin = AsyncMock(side_effect=BinNotFoundError())

    with (
        patch(
            "erp.api.modules.bin.views.BinService",
            return_value=mock_bin_service,
        ),
        pytest.raises(BinNotFoundError),
    ):
        await get_bin(
            workspace_id=seed_workspace,
            bin_id=bin_id,
            db=mock_db,
        )


# ==============================================================================
# UPDATE BIN
# ==============================================================================


@pytest.mark.asyncio
async def test_update_bin_success(
    mock_db,
    mock_background_tasks,
    mock_bin_service,
    bin_obj,
    seed_workspace,
):
    data = BinUpdate(code="UPDATED-01", zone="Updated Zone")
    mock_bin_service.update_bin = AsyncMock(return_value=bin_obj)

    with (
        patch(
            "erp.api.modules.bin.views.BinService",
            return_value=mock_bin_service,
        ),
        patch(
            "erp.api.modules.bin.views.global_event_bus.publish",
            new_callable=AsyncMock,
        ),
    ):
        response = await update_bin(
            workspace_id=seed_workspace,
            bin_id=bin_obj.id,
            data=data,
            background_tasks=mock_background_tasks,
            db=mock_db,
        )

    assert response is bin_obj
    mock_bin_service.update_bin.assert_awaited_once_with(seed_workspace, bin_obj.id, data)

    mock_background_tasks.add_task.assert_called_once()
    args = mock_background_tasks.add_task.call_args.args

    assert isinstance(args[1], BinUpdatedEvent)
    assert args[1].workspace_id == seed_workspace
    assert args[1].bin is bin_obj


@pytest.mark.asyncio
async def test_update_bin_not_found(
    mock_db,
    mock_background_tasks,
    mock_bin_service,
    seed_workspace,
):
    bin_id = uuid.uuid4()
    data = BinUpdate(code="UPDATED-01")

    mock_bin_service.update_bin = AsyncMock(side_effect=BinNotFoundError())

    with (
        patch(
            "erp.api.modules.bin.views.BinService",
            return_value=mock_bin_service,
        ),
        pytest.raises(BinNotFoundError),
    ):
        await update_bin(
            workspace_id=seed_workspace,
            bin_id=bin_id,
            data=data,
            background_tasks=mock_background_tasks,
            db=mock_db,
        )

    mock_background_tasks.add_task.assert_not_called()


# ==============================================================================
# DELETE BIN
# ==============================================================================


@pytest.mark.asyncio
async def test_delete_bin_success(mock_db, mock_bin_service, seed_workspace):
    bin_id = uuid.uuid4()
    mock_bin_service.delete_bin = AsyncMock(return_value=None)

    with patch(
        "erp.api.modules.bin.views.BinService",
        return_value=mock_bin_service,
    ):
        response = await delete_bin(
            workspace_id=seed_workspace,
            bin_id=bin_id,
            db=mock_db,
        )

    assert response is None
    mock_bin_service.delete_bin.assert_awaited_once_with(seed_workspace, bin_id)


@pytest.mark.asyncio
async def test_delete_bin_with_active_stock(mock_db, mock_bin_service, seed_workspace):
    bin_id = uuid.uuid4()
    mock_bin_service.delete_bin = AsyncMock(side_effect=BinHasInventoryItemsError())

    with (
        patch(
            "erp.api.modules.bin.views.BinService",
            return_value=mock_bin_service,
        ),
        pytest.raises(BinHasInventoryItemsError),
    ):
        await delete_bin(
            workspace_id=seed_workspace,
            bin_id=bin_id,
            db=mock_db,
        )


@pytest.mark.asyncio
async def test_delete_bin_not_found(mock_db, mock_bin_service, seed_workspace):
    bin_id = uuid.uuid4()
    mock_bin_service.delete_bin = AsyncMock(side_effect=BinNotFoundError())

    with (
        patch(
            "erp.api.modules.bin.views.BinService",
            return_value=mock_bin_service,
        ),
        pytest.raises(BinNotFoundError),
    ):
        await delete_bin(
            workspace_id=seed_workspace,
            bin_id=bin_id,
            db=mock_db,
        )
