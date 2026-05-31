from typing import Annotated

from fastapi import Depends

from erp.api.modules.orders.adapter import StandardOrderAdapter
from erp.api.modules.orders.client import StandardClient
from erp.api.modules.orders.service import OrderService


def get_client() -> StandardClient:
    return StandardClient()


def get_adapter(
    client: Annotated[StandardClient, Depends(get_client)]
) -> StandardOrderAdapter:
    return StandardOrderAdapter(client)


def get_order_service(
    adapter: Annotated[StandardOrderAdapter, Depends(get_adapter)]
) -> OrderService:
    return OrderService(adapter)
