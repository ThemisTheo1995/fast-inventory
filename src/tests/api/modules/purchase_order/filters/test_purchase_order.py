import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from erp.api.modules.purchase_order.enums import POStatusEnum
from erp.api.modules.purchase_order.filters.purchase_order import (
    PurchaseOrderFilter,
    get_po_amount_range,
)
from erp.api.modules.purchase_order.models import PurchaseOrder

# ============================================================================
# Unit Tests for get_po_amount_range (Mocked DB)
# ============================================================================


@pytest.mark.asyncio
async def test_get_po_amount_range_empty_database():
    """Returns fallback range and step when no purchase orders exist."""
    db_mock = AsyncMock(spec=AsyncSession)
    result_mock = MagicMock()
    result_mock.first.return_value = (None, None)
    db_mock.execute.return_value = result_mock

    amount_range = await get_po_amount_range(db_mock, uuid.uuid4())

    assert amount_range == (0, 10000, 500)


@pytest.mark.asyncio
async def test_get_po_amount_range_normal_bounds():
    """Returns rounded bounds and a dynamically calculated step."""
    db_mock = AsyncMock(spec=AsyncSession)
    result_mock = MagicMock()
    result_mock.first.return_value = (1500, 4500)
    db_mock.execute.return_value = result_mock

    min_amt, max_amt, step = await get_po_amount_range(
        db_mock,
        uuid.uuid4(),
    )

    assert min_amt <= 1500
    assert max_amt >= 4500
    assert step > 0
    assert (max_amt - min_amt) / step <= 21


@pytest.mark.asyncio
async def test_get_po_amount_range_equal_min_max():
    """Returns a useful slider range when all POs have the same amount."""
    db_mock = AsyncMock(spec=AsyncSession)
    result_mock = MagicMock()
    result_mock.first.return_value = (10, 10)
    db_mock.execute.return_value = result_mock

    min_amt, max_amt, step = await get_po_amount_range(
        db_mock,
        uuid.uuid4(),
    )

    assert min_amt < 10
    assert max_amt > 10
    assert step > 0
    assert min_amt <= 10 <= max_amt


@pytest.mark.asyncio
async def test_get_po_amount_range_single_large_amount():
    """Handles a single large PO amount without producing a narrow range."""
    db_mock = AsyncMock(spec=AsyncSession)
    result_mock = MagicMock()
    result_mock.first.return_value = (2500, 2500)
    db_mock.execute.return_value = result_mock

    min_amt, max_amt, step = await get_po_amount_range(
        db_mock,
        uuid.uuid4(),
    )

    assert min_amt < 2500
    assert max_amt > 2500
    assert step > 0


# ============================================================================
# Filter SQL Compilation Tests
# ============================================================================


def test_purchase_order_filter_apply_status():
    """Applies status equality filter to the query."""
    base_query = select(PurchaseOrder)
    status_val = next(iter(POStatusEnum))

    po_filter = PurchaseOrderFilter(status=status_val)
    filtered_query = po_filter.apply(base_query, PurchaseOrder)

    compiled = str(
        filtered_query.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert f"purchase_orders.status = '{status_val.value}'" in compiled


def test_purchase_order_filter_apply_amount_between_range():
    """Applies total_amount BETWEEN operator when a range string is passed."""
    base_query = select(PurchaseOrder)

    po_filter = PurchaseOrderFilter(total_amount="1000,5000")
    filtered_query = po_filter.apply(base_query, PurchaseOrder)

    compiled = str(
        filtered_query.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "purchase_orders.total_amount BETWEEN 1000.0 AND 5000.0" in compiled


# ============================================================================
# Integration Tests with Async Database Session
# ============================================================================


@pytest.mark.asyncio
async def test_get_po_amount_range_db_isolation(
    db_session: AsyncSession,
    seed_workspace,
    alt_workspace,
):
    """Ignores deleted POs and POs belonging to other workspaces."""

    status = next(iter(POStatusEnum))

    po1 = PurchaseOrder(
        po_number="PO-1",
        workspace_id=seed_workspace,
        total_amount=3500,
        status=status,
    )
    po2 = PurchaseOrder(
        po_number="PO-2",
        workspace_id=seed_workspace,
        total_amount=8200,
        status=status,
    )
    po_deleted = PurchaseOrder(
        po_number="PO-DELETED",
        workspace_id=seed_workspace,
        total_amount=50000,
        is_deleted=True,
        status=status,
    )
    po_other = PurchaseOrder(
        po_number="PO-OTHER",
        workspace_id=alt_workspace,
        total_amount=100,
        status=status,
    )

    db_session.add_all([po1, po2, po_deleted, po_other])
    await db_session.flush()

    min_amt, max_amt, step = await get_po_amount_range(
        db_session,
        seed_workspace,
    )

    assert min_amt <= 3500
    assert max_amt >= 8200
    assert max_amt < 50000
    assert min_amt > 100
    assert step > 0
