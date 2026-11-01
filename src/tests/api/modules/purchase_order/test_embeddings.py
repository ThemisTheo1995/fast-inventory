import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from erp.api.modules.purchase_order.embeddings import (
    process_purchase_order_search_index,
)
from erp.api.search.enums import EntityTypeEnum
from erp.api.search.models import GlobalSearchIndex


@pytest.fixture
def purchase_order():
    supplier = SimpleNamespace(
        name="Acme Supplies",
        email="orders@acme.com",
    )

    item = SimpleNamespace(title="Test Item")

    line = SimpleNamespace(
        quantity=5,
        item=item,
    )

    return SimpleNamespace(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        po_number="PO-001",
        supplier=supplier,
        purchase_order_lines=[line],
        status=SimpleNamespace(label="Sent"),
        total_amount=500,
        is_deleted=False,
    )


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.add = MagicMock()
    return db


@pytest.fixture
def mock_session_context(mock_db):
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=mock_db)
    context.__aexit__ = AsyncMock(return_value=None)
    return context


@pytest.mark.asyncio
async def test_process_purchase_order_search_index_returns_when_order_not_found(
    mock_db,
    mock_session_context,
):
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = result

    with (
        patch(
            "erp.api.modules.purchase_order.embeddings.AsyncSessionLocal",
            return_value=mock_session_context,
        ),
        patch("erp.api.modules.purchase_order.embeddings.generate_embedding") as mock_embedding,
    ):
        await process_purchase_order_search_index(uuid.uuid4())

    mock_embedding.assert_not_called()
    mock_db.commit.assert_not_called()
    mock_db.add.assert_not_called()


@pytest.mark.asyncio
async def test_process_purchase_order_search_index_returns_when_order_deleted(
    purchase_order,
    mock_db,
    mock_session_context,
):
    purchase_order.is_deleted = True

    result = MagicMock()
    result.scalar_one_or_none.return_value = purchase_order
    mock_db.execute.return_value = result

    with (
        patch(
            "erp.api.modules.purchase_order.embeddings.AsyncSessionLocal",
            return_value=mock_session_context,
        ),
        patch("erp.api.modules.purchase_order.embeddings.generate_embedding") as mock_embedding,
    ):
        await process_purchase_order_search_index(purchase_order.id)

    mock_embedding.assert_not_called()
    mock_db.commit.assert_not_called()
    mock_db.add.assert_not_called()


@pytest.mark.asyncio
async def test_process_purchase_order_search_index_creates_new_index(
    purchase_order,
    mock_db,
    mock_session_context,
):
    purchase_order_result = MagicMock()
    purchase_order_result.scalar_one_or_none.return_value = purchase_order

    index_result = MagicMock()
    index_result.scalar_one_or_none.return_value = None

    mock_db.execute.side_effect = [
        purchase_order_result,
        index_result,
    ]

    embedding = [0.1, 0.2, 0.3]

    with (
        patch(
            "erp.api.modules.purchase_order.embeddings.AsyncSessionLocal",
            return_value=mock_session_context,
        ),
        patch(
            "erp.api.modules.purchase_order.embeddings.generate_embedding",
            return_value=embedding,
        ) as mock_embedding,
    ):
        await process_purchase_order_search_index(purchase_order.id)

    mock_embedding.assert_called_once()
    embedded_text = mock_embedding.call_args.args[0]

    assert "Document Type: Purchase Order." in embedded_text
    assert "Purchase Order Number (PO Number): PO-001" in embedded_text
    assert "Supplier Name: Acme Supplies\norders@acme.com" in embedded_text
    assert "Purchase Order Status: Sent" in embedded_text
    assert "Total Amount: 500" in embedded_text
    assert "Line Items Ordered: 5x Test Item." in embedded_text

    mock_db.add.assert_called_once()

    created_index = mock_db.add.call_args.args[0]

    assert isinstance(created_index, GlobalSearchIndex)
    assert created_index.workspace_id == purchase_order.workspace_id
    assert created_index.entity_type == EntityTypeEnum.PURCHASE_ORDER
    assert created_index.entity_id == purchase_order.id
    assert created_index.title == "PO #PO-001"
    assert "Supplier: Acme Supplies" in created_index.snippet
    assert created_index.url == f"/purchase-orders/{purchase_order.id}"
    assert created_index.embedding == embedding

    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_purchase_order_search_index_updates_existing_index(
    purchase_order,
    mock_db,
    mock_session_context,
):
    existing_index = SimpleNamespace(
        title="Old title",
        snippet="Old snippet",
        url="old-url",
        embedding=[0.9],
    )

    purchase_order_result = MagicMock()
    purchase_order_result.scalar_one_or_none.return_value = purchase_order

    index_result = MagicMock()
    index_result.scalar_one_or_none.return_value = existing_index

    mock_db.execute.side_effect = [
        purchase_order_result,
        index_result,
    ]

    embedding = [0.1, 0.2, 0.3]

    with (
        patch(
            "erp.api.modules.purchase_order.embeddings.AsyncSessionLocal",
            return_value=mock_session_context,
        ),
        patch(
            "erp.api.modules.purchase_order.embeddings.generate_embedding",
            return_value=embedding,
        ),
    ):
        await process_purchase_order_search_index(purchase_order.id)

    assert existing_index.title == "PO #PO-001"
    assert "Supplier:" in existing_index.snippet
    assert existing_index.url == f"/purchase-orders/{purchase_order.id}"
    assert existing_index.embedding == embedding

    mock_db.add.assert_not_called()
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_purchase_order_search_index_handles_no_active_lines(
    purchase_order,
    mock_db,
    mock_session_context,
):
    purchase_order.purchase_order_lines = []

    purchase_order_result = MagicMock()
    purchase_order_result.scalar_one_or_none.return_value = purchase_order

    index_result = MagicMock()
    index_result.scalar_one_or_none.return_value = None

    mock_db.execute.side_effect = [
        purchase_order_result,
        index_result,
    ]

    with (
        patch(
            "erp.api.modules.purchase_order.embeddings.AsyncSessionLocal",
            return_value=mock_session_context,
        ),
        patch(
            "erp.api.modules.purchase_order.embeddings.generate_embedding",
            return_value=[0.1, 0.2],
        ) as mock_embedding,
    ):
        await process_purchase_order_search_index(purchase_order.id)

    embedded_text = mock_embedding.call_args.args[0]

    assert "No active line items" in embedded_text

    mock_db.add.assert_called_once()
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_purchase_order_search_index_handles_missing_item(
    purchase_order,
    mock_db,
    mock_session_context,
):
    purchase_order.purchase_order_lines = [SimpleNamespace(quantity=3, item=None)]

    purchase_order_result = MagicMock()
    purchase_order_result.scalar_one_or_none.return_value = purchase_order

    index_result = MagicMock()
    index_result.scalar_one_or_none.return_value = None

    mock_db.execute.side_effect = [
        purchase_order_result,
        index_result,
    ]

    with (
        patch(
            "erp.api.modules.purchase_order.embeddings.AsyncSessionLocal",
            return_value=mock_session_context,
        ),
        patch(
            "erp.api.modules.purchase_order.embeddings.generate_embedding",
            return_value=[0.1, 0.2],
        ) as mock_embedding,
    ):
        await process_purchase_order_search_index(purchase_order.id)

    embedded_text = mock_embedding.call_args.args[0]

    assert "Unknown Item" in embedded_text
    assert "3x Unknown Item" in embedded_text

    mock_db.add.assert_called_once()
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_purchase_order_search_index_uses_item_name_when_available(
    purchase_order,
    mock_db,
    mock_session_context,
):
    purchase_order.purchase_order_lines = [
        SimpleNamespace(
            quantity=2,
            item=SimpleNamespace(name="Named Item", title="Fallback Title"),
        )
    ]

    purchase_order_result = MagicMock()
    purchase_order_result.scalar_one_or_none.return_value = purchase_order

    index_result = MagicMock()
    index_result.scalar_one_or_none.return_value = None

    mock_db.execute.side_effect = [
        purchase_order_result,
        index_result,
    ]

    with (
        patch(
            "erp.api.modules.purchase_order.embeddings.AsyncSessionLocal",
            return_value=mock_session_context,
        ),
        patch(
            "erp.api.modules.purchase_order.embeddings.generate_embedding",
            return_value=[0.1, 0.2],
        ) as mock_embedding,
    ):
        await process_purchase_order_search_index(purchase_order.id)

    embedded_text = mock_embedding.call_args.args[0]

    assert "2x Named Item" in embedded_text
    assert "Fallback Title" not in embedded_text

    mock_db.commit.assert_awaited_once()
