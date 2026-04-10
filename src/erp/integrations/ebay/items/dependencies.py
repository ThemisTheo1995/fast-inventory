from typing import Annotated

from fastapi import Depends

from erp.integrations.ebay.items.adapter import EbayItemAdapter
from erp.integrations.ebay.items.client import EbayItemClient
from erp.integrations.ebay.items.service import EbayItemService


def get_client() -> EbayItemClient:
    return EbayItemClient()


def get_adapter(
    client: Annotated[EbayItemClient, Depends(get_client)]
) -> EbayItemAdapter:
    return EbayItemAdapter(client)


def get_ebay_service(
    adapter: Annotated[EbayItemAdapter, Depends(get_adapter)]
) -> EbayItemService:
    return EbayItemService(adapter)
