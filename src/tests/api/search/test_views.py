from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from erp.api.search.schemas import SearchResult
from erp.api.search.views import global_search


@pytest.mark.asyncio
async def test_global_search_returns_results():
    workspace_id = uuid4()
    db = AsyncMock()

    expected_results = [
        SearchResult(
            entity_type="item",
            entity_id=uuid4(),
            title="Test Item",
            url="/items/test-item",
        )
    ]

    with patch("erp.api.search.views.GlobalSearchService") as mock_service_class:
        mock_service = mock_service_class.return_value
        mock_service.search = AsyncMock(return_value=expected_results)

        response = await global_search(
            workspace_id=workspace_id,
            db=db,
            q="test item",
            limit=10,
        )

    assert response == expected_results

    mock_service_class.assert_called_once_with(db)

    mock_service.search.assert_awaited_once_with(
        workspace_id=workspace_id,
        query_text="test item",
        limit=10,
    )


@pytest.mark.asyncio
async def test_global_search_passes_custom_limit():
    workspace_id = uuid4()
    db = AsyncMock()

    with patch("erp.api.search.views.GlobalSearchService") as mock_service_class:
        mock_service = mock_service_class.return_value
        mock_service.search = AsyncMock(return_value=[])

        response = await global_search(
            workspace_id=workspace_id,
            db=db,
            q="customer",
            limit=3,
        )

    assert response == []

    mock_service.search.assert_awaited_once_with(
        workspace_id=workspace_id,
        query_text="customer",
        limit=3,
    )


@pytest.mark.asyncio
async def test_global_search_uses_default_limit():
    workspace_id = uuid4()
    db = AsyncMock()

    with patch("erp.api.search.views.GlobalSearchService") as mock_service_class:
        mock_service = mock_service_class.return_value
        mock_service.search = AsyncMock(return_value=[])

        await global_search(
            workspace_id=workspace_id,
            db=db,
            q="test",
        )

    mock_service.search.assert_awaited_once_with(
        workspace_id=workspace_id,
        query_text="test",
        limit=10,
    )


@pytest.mark.asyncio
async def test_global_search_propagates_service_error():
    workspace_id = uuid4()
    db = AsyncMock()

    with (
        patch("erp.api.search.views.GlobalSearchService") as mock_service_class,
        pytest.raises(RuntimeError, match="Search failed"),
    ):
        mock_service = mock_service_class.return_value
        mock_service.search = AsyncMock(side_effect=RuntimeError("Search failed"))

        await global_search(
            workspace_id=workspace_id,
            db=db,
            q="test",
        )
