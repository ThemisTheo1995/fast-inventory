
from typing import Annotated

from fastapi import APIRouter, Depends

from erp.api.modules.orders.dependencies import get_order_service
from erp.api.modules.orders.schemas import MarketplaceCreateOrder, MarketplaceOrder
from erp.api.modules.orders.service import OrderService

router = APIRouter()


@router.get("/", response_model=list[MarketplaceOrder])
def list_orders(
    service: Annotated[OrderService, Depends(get_order_service)]
) -> list[MarketplaceOrder]:
    """List all orders from the marketplace."""
    return service.list_orders()


@router.post("/create", response_model=MarketplaceOrder, tags=["Orders"])
def create_order(
    order_data: MarketplaceCreateOrder,
    service: Annotated[OrderService, Depends(get_order_service)]
) -> MarketplaceOrder:
    """Create a new order in the ERP through the marketplace."""
    return service.create_order(order_data)
