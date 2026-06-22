from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from src.erp.integrations.ebay.items.adapter import EbayItemAdapter
from src.erp.integrations.ebay.items.client import EbayItemClient
from src.erp.integrations.ebay.items.dependencies import (
    get_adapter,
    get_client,
    get_ebay_service,
    get_repository,
)
from src.erp.integrations.ebay.items.repository import EbayItemRepository
from src.erp.integrations.ebay.items.service import EbayItemService

# ============================================================================
# FASTAPI DEPENDENCY FACTORY UNIT TESTS
# ============================================================================


def test_get_client_instantiates_client_directly():
    """
    get_client must return a fresh standalone instance of the EbayItemClient.
    """
    client = get_client()

    assert client is not None
    assert isinstance(client, EbayItemClient)


def test_get_adapter_binds_injected_client():
    """
    get_adapter must accept an EbayItemClient dependency and return an
    EbayItemAdapter instance wrapped around it.
    """
    # Arrange
    mock_client = MagicMock(spec=EbayItemClient)

    # Act
    adapter = get_adapter(client=mock_client)

    # Assert
    assert adapter is not None
    assert isinstance(adapter, EbayItemAdapter)
    assert adapter.client == mock_client


def test_get_repository_binds_injected_db_session():
    """
    get_repository must receive the database Session dependency and pass it
    straight through to the underlying EbayItemRepository constructor.
    """
    # Arrange
    mock_db = MagicMock(spec=Session)

    # Act
    repo = get_repository(db=mock_db)

    # Assert
    assert repo is not None
    assert isinstance(repo, EbayItemRepository)
    assert repo.db == mock_db


def test_get_ebay_service_orchestrates_dependencies():
    """
    get_ebay_service must successfully accept structural adapter and
    repository components to resolve the top-level EbayItemService layer.
    """
    # Arrange
    mock_adapter = MagicMock(spec=EbayItemAdapter)
    mock_repository = MagicMock(spec=EbayItemRepository)

    # Act
    service = get_ebay_service(adapter=mock_adapter, repository=mock_repository)

    # Assert
    assert service is not None
    assert isinstance(service, EbayItemService)
    assert service.adapter == mock_adapter
    assert service.repository == mock_repository
