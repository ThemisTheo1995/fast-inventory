from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from pydantic import ValidationError

from erp.api.search.enums import EntityTypeEnum
from erp.api.search.schemas import SearchResult
from erp.api.search.service import GlobalSearchService


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def service(mock_db):
    return GlobalSearchService(mock_db)


@pytest.fixture
def workspace_id():
    return uuid4()


@pytest.fixture
def search_records():
    return [
        SimpleNamespace(
            entity_type=EntityTypeEnum.ITEM.value,
            entity_id=uuid4(),
            title="Test Item",
            url="/items/test-item",
        ),
        SimpleNamespace(
            entity_type=EntityTypeEnum.CUSTOMER.value,
            entity_id=uuid4(),
            title="Test Customer",
            url="/customers/test-customer",
        ),
    ]


@pytest.mark.asyncio
async def test_search_returns_matching_results(
    service,
    mock_db,
    workspace_id,
    search_records,
):
    result = MagicMock()
    result.scalars.return_value.all.return_value = search_records
    mock_db.execute.return_value = result

    query_vector = [0.1, 0.2, 0.3]

    with patch(
        "erp.api.search.service.generate_embedding",
        return_value=query_vector,
    ) as mock_embedding:
        response = await service.search(
            workspace_id=workspace_id,
            query_text="test search",
        )

    mock_embedding.assert_called_once_with("test search")
    mock_db.execute.assert_awaited_once()

    assert len(response) == 2
    assert all(isinstance(item, SearchResult) for item in response)

    assert response[0].entity_type == EntityTypeEnum.ITEM.value
    assert response[0].title == "Test Item"
    assert response[0].url == "/items/test-item"

    assert response[1].entity_type == EntityTypeEnum.CUSTOMER.value
    assert response[1].title == "Test Customer"


@pytest.mark.asyncio
async def test_search_returns_empty_list(
    service,
    mock_db,
    workspace_id,
):
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = result

    with patch(
        "erp.api.search.service.generate_embedding",
        return_value=[0.1, 0.2, 0.3],
    ):
        response = await service.search(
            workspace_id=workspace_id,
            query_text="nothing found",
        )

    assert response == []
    mock_db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_search_uses_custom_limit(
    service,
    mock_db,
    workspace_id,
):
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = result

    with patch(
        "erp.api.search.service.generate_embedding",
        return_value=[0.1, 0.2, 0.3],
    ):
        await service.search(
            workspace_id=workspace_id,
            query_text="test",
            limit=5,
        )

    statement = mock_db.execute.call_args.args[0]

    assert statement._limit_clause.value == 5


@pytest.mark.asyncio
async def test_search_uses_default_limit(
    service,
    mock_db,
    workspace_id,
):
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = result

    with patch(
        "erp.api.search.service.generate_embedding",
        return_value=[0.1, 0.2, 0.3],
    ):
        await service.search(
            workspace_id=workspace_id,
            query_text="test",
        )

    statement = mock_db.execute.call_args.args[0]

    assert statement._limit_clause.value == 10


@pytest.mark.asyncio
async def test_search_propagates_database_error(
    service,
    mock_db,
    workspace_id,
):
    mock_db.execute.side_effect = RuntimeError("Database error")

    with (
        patch(
            "erp.api.search.service.generate_embedding",
            return_value=[0.1, 0.2, 0.3],
        ),
        pytest.raises(RuntimeError, match="Database error"),
    ):
        await service.search(
            workspace_id=workspace_id,
            query_text="test",
        )


@pytest.mark.asyncio
async def test_search_propagates_embedding_error(
    service,
    mock_db,
    workspace_id,
):
    with (
        patch(
            "erp.api.search.service.generate_embedding",
            side_effect=RuntimeError("Embedding error"),
        ),
        pytest.raises(RuntimeError, match="Embedding error"),
    ):
        await service.search(
            workspace_id=workspace_id,
            query_text="test",
        )

    mock_db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_search_rejects_invalid_search_records(
    service,
    mock_db,
    workspace_id,
):
    invalid_record = SimpleNamespace(
        entity_type="item",
        entity_id="not-a-valid-uuid",
        title="Invalid Item",
        url="/items/invalid",
    )

    result = MagicMock()
    result.scalars.return_value.all.return_value = [invalid_record]
    mock_db.execute.return_value = result

    with (
        patch(
            "erp.api.search.service.generate_embedding",
            return_value=[0.1, 0.2, 0.3],
        ),
        pytest.raises(ValidationError),
    ):
        await service.search(
            workspace_id=workspace_id,
            query_text="test",
        )
