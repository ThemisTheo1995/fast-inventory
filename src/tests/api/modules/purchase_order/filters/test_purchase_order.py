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
    """Returns fallback (0, 10000) when no purchase orders exist."""
    db_mock = AsyncMock(spec=AsyncSession)
    result_mock = MagicMock()
    result_mock.first.return_value = (None, None)
    db_mock.execute.return_value = result_mock

    workspace_id = uuid.uuid4()
    amount_range = await get_po_amount_range(db_mock, workspace_id)

    assert amount_range == (0, 10000)


@pytest.mark.asyncio
async def test_get_po_amount_range_normal_bounds():
    """Rounds min down and max up to the nearest step (2000)."""
    db_mock = AsyncMock(spec=AsyncSession)
    result_mock = MagicMock()
    # Min = 1500 -> floor to 0; Max = 4500 -> ceil to 6000
    result_mock.first.return_value = (1500, 4500)
    db_mock.execute.return_value = result_mock

    workspace_id = uuid.uuid4()
    amount_range = await get_po_amount_range(db_mock, workspace_id)

    assert amount_range == (0, 6000)


@pytest.mark.asyncio
async def test_get_po_amount_range_equal_min_max():
    """Ensures a movable range when all POs have the exact same amount."""
    db_mock = AsyncMock(spec=AsyncSession)
    result_mock = MagicMock()
    # Min = 2500, Max = 2500 -> clean_min = 2000, clean_max = 2000
    result_mock.first.return_value = (2500, 2500)
    db_mock.execute.return_value = result_mock

    workspace_id = uuid.uuid4()
    amount_range = await get_po_amount_range(db_mock, workspace_id)

    # Should expand max by step (2000)
    assert amount_range == (2000, 4000)


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

    print(compiled)

    assert "purchase_orders.total_amount BETWEEN 1000.0 AND 5000.0" in compiled


# ============================================================================
# Integration Tests with Async Database Session (Optional / DB-backed)
# ============================================================================


@pytest.mark.asyncio
async def test_get_po_amount_range_db_isolation(db_session: AsyncSession, seed_workspace, alt_workspace):
    """Verifies deleted POs and other workspace POs are ignored in DB query."""

    # Create test POs
    po1 = PurchaseOrder(
        po_number="PO-1",
        workspace_id=seed_workspace,
        total_amount=3500,
        status=next(iter(POStatusEnum)),
    )
    po2 = PurchaseOrder(
        po_number="PO-2",
        workspace_id=seed_workspace,
        total_amount=8200,
        status=next(iter(POStatusEnum)),
    )
    # Deleted PO in same workspace (should be ignored)
    po_deleted = PurchaseOrder(
        po_number="PO-DELETED",
        workspace_id=seed_workspace,
        total_amount=50000,
        is_deleted=True,
        status=next(iter(POStatusEnum)),
    )
    # PO in another workspace (should be ignored)
    po_other = PurchaseOrder(
        po_number="PO-OTHER",
        workspace_id=alt_workspace,
        total_amount=100,
        status=next(iter(POStatusEnum)),
    )

    db_session.add_all([po1, po2, po_deleted, po_other])
    await db_session.flush()

    # Execute range query
    min_amt, max_amt = await get_po_amount_range(db_session, seed_workspace)

    # 3500 floors to 2000; 8200 ceils to 10000
    assert min_amt == 2000
    assert max_amt == 10000
