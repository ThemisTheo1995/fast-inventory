from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from erp.database.base import get_db
from erp.integrations.ebay.orders.adapter import EbayOrderAdapter
from erp.integrations.ebay.orders.client import EbayOrderClient
from erp.integrations.ebay.orders.repository import EbayOrderRepository
from erp.integrations.ebay.orders.service import EbayOrderService


def get_client() -> EbayOrderClient:
    return EbayOrderClient()


def get_adapter(
    client: Annotated[EbayOrderClient, Depends(get_client)]
) -> EbayOrderAdapter:
    return EbayOrderAdapter(client)


def get_repository(db: Annotated[Session, Depends(get_db)]) -> EbayOrderRepository:
    return EbayOrderRepository(db)


def get_ebay_service(
    adapter: Annotated[EbayOrderAdapter, Depends(get_adapter)],
    repository: Annotated[EbayOrderRepository, Depends(get_repository)]
) -> EbayOrderService:
    return EbayOrderService(adapter, repository)
