from typing import Annotated

from fastapi import Depends

from erp.integrations.ebay.orders.adapter import EbayOrderAdapter
from erp.integrations.ebay.orders.client import EbayOrderClient
from erp.integrations.ebay.orders.service import EbayOrderService


def get_client() -> EbayOrderClient:
    return EbayOrderClient()


def get_adapter(
    client: Annotated[EbayOrderClient, Depends(get_client)]
) -> EbayOrderAdapter:
    return EbayOrderAdapter(client)


def get_ebay_service(
    adapter: Annotated[EbayOrderAdapter, Depends(get_adapter)]
) -> EbayOrderService:
    return EbayOrderService(adapter)
