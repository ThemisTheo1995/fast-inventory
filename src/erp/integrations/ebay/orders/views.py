from typing import Annotated

from fastapi import APIRouter, Depends

from erp.integrations.ebay.orders.dependencies import get_ebay_service
from erp.integrations.ebay.orders.service import EbayOrderService
from erp.modules.orders.schemas import MarketplaceOrder

router = APIRouter()


@router.get("/", response_model=list[MarketplaceOrder])
def get_orders(
    service: Annotated[EbayOrderService, Depends(get_ebay_service)]
) -> list[MarketplaceOrder]:
    """
    Fetch eBay orders (via ERP mapping layer)
    """
    return service.get_orders()


@router.post("/sync", response_model=list[MarketplaceOrder])
def sync_orders(
    service: Annotated[EbayOrderService, Depends(get_ebay_service)]
) -> list[MarketplaceOrder]:
    """
    Trigger manual sync from eBay
    (useful for FE button or cron jobs)
    """
    return service.sync_orders()
