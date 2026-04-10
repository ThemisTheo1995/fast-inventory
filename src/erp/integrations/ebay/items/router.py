from typing import Annotated

from fastapi import APIRouter, Depends

from erp.integrations.ebay.items.dependencies import get_ebay_service
from erp.integrations.ebay.items.schemas import EbayItem
from erp.integrations.ebay.items.service import EbayItemService

router = APIRouter()


@router.get("/", response_model=list[EbayItem])
def get_items(
    service: Annotated[EbayItemService, Depends(get_ebay_service)]
) -> list[EbayItem]:
    """
    Fetch eBay items (via ERP mapping layer)
    """
    return service.get_items()


@router.post("/sync", response_model=list[EbayItem])
def sync_items(
    service: Annotated[EbayItemService, Depends(get_ebay_service)]
) -> list[EbayItem]:
    """
    Trigger manual sync from eBay
    (useful for FE button or cron jobs)
    """
    return service.sync_items()
