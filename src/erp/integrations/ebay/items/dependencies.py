from typing import Annotated

from fastapi import Depends

from src.erp.database.base import Session, get_db
from src.erp.integrations.ebay.items.adapter import EbayItemAdapter
from src.erp.integrations.ebay.items.client import EbayItemClient
from src.erp.integrations.ebay.items.repository import EbayItemRepository
from src.erp.integrations.ebay.items.service import EbayItemService


def get_client() -> EbayItemClient:
    return EbayItemClient()


def get_adapter(client: Annotated[EbayItemClient, Depends(get_client)]) -> EbayItemAdapter:
    return EbayItemAdapter(client)


def get_repository(db: Annotated[Session, Depends(get_db)]) -> EbayItemRepository:
    return EbayItemRepository(db)


def get_ebay_service(
    adapter: Annotated[EbayItemAdapter, Depends(get_adapter)],
    repository: Annotated[EbayItemRepository, Depends(get_repository)],
) -> EbayItemService:
    return EbayItemService(adapter, repository)
