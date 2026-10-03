import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from erp.api.modules.supplier.embeddings import process_supplier_search_index
from erp.api.modules.supplier.models import Supplier
from erp.api.search.enums import EntityTypeEnum
from erp.api.search.models import GlobalSearchIndex


@pytest.mark.asyncio
@patch("erp.api.modules.supplier.embeddings.AsyncSessionLocal")
@patch("erp.api.modules.supplier.embeddings.generate_embedding")
async def test_process_supplier_search_index_creates_new(
    mock_generate_embedding, mock_async_session_local, db_session, active_supplier
):
    """Verifies that indexing a new supplier successfully creates a GlobalSearchIndex record."""
    mock_generate_embedding.return_value = [0.1] * 768

    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__.return_value = db_session
    mock_async_session_local.return_value = mock_session_ctx

    await process_supplier_search_index(active_supplier.id)

    # 1. Ensure embedding generation was triggered
    mock_generate_embedding.assert_called_once()

    # 2. Verify record exists and has correct attributes
    result = await db_session.execute(
        select(GlobalSearchIndex).where(GlobalSearchIndex.entity_id == active_supplier.id)
    )
    record = result.scalar_one_or_none()

    assert record is not None
    assert record.title == active_supplier.name
    assert record.snippet == f"Email: {active_supplier.email}"
    assert record.url == f"/suppliers/{active_supplier.id}"
    assert record.entity_type == EntityTypeEnum.SUPPLIER
    assert record.workspace_id == active_supplier.workspace_id


@pytest.mark.asyncio
@patch("erp.api.modules.supplier.embeddings.AsyncSessionLocal")
@patch("erp.api.modules.supplier.embeddings.generate_embedding")
async def test_process_supplier_search_index_updates_existing(
    mock_generate_embedding, mock_async_session_local, db_session, active_supplier
):
    """Verifies that indexing an existing search record updates it instead of duplicating."""
    mock_generate_embedding.return_value = [0.2] * 768

    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__.return_value = db_session
    mock_async_session_local.return_value = mock_session_ctx

    # Pre-seed a stale index record
    stale_record = GlobalSearchIndex(
        workspace_id=active_supplier.workspace_id,
        entity_type=EntityTypeEnum.SUPPLIER,
        entity_id=active_supplier.id,
        title="Stale Title",
        snippet="Stale Snippet",
        url="/old-url",
        embedding=[0.0] * 768,
    )
    db_session.add(stale_record)
    await db_session.flush()

    await process_supplier_search_index(active_supplier.id)

    # Verify update happened and no duplicates were created
    result = await db_session.execute(
        select(GlobalSearchIndex).where(GlobalSearchIndex.entity_id == active_supplier.id)
    )
    records = result.scalars().all()

    assert len(records) == 1
    assert records[0].title == active_supplier.name
    assert records[0].url == f"/suppliers/{active_supplier.id}"


@pytest.mark.asyncio
@patch("erp.api.modules.supplier.embeddings.AsyncSessionLocal")
@patch("erp.api.modules.supplier.embeddings.generate_embedding")
async def test_process_supplier_search_index_skips_nonexistent(
    mock_generate_embedding, mock_async_session_local, db_session
):
    """Verifies early return if the supplier UUID does not exist in the database."""
    fake_id = uuid.uuid4()

    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__.return_value = db_session
    mock_async_session_local.return_value = mock_session_ctx

    await process_supplier_search_index(fake_id)

    mock_generate_embedding.assert_not_called()


@pytest.mark.asyncio
@patch("erp.api.modules.supplier.embeddings.AsyncSessionLocal")
@patch("erp.api.modules.supplier.embeddings.generate_embedding")
async def test_process_supplier_search_index_skips_deleted(
    mock_generate_embedding, mock_async_session_local, db_session, seed_workspace
):
    """Verifies early return if the supplier is soft-deleted."""
    deleted_supplier = Supplier(
        workspace_id=seed_workspace,
        name="Defunct Supply Co",
        email="defunct@supply.org",
        is_deleted=True,
    )
    db_session.add(deleted_supplier)
    await db_session.flush()

    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__.return_value = db_session
    mock_async_session_local.return_value = mock_session_ctx

    await process_supplier_search_index(deleted_supplier.id)

    mock_generate_embedding.assert_not_called()
