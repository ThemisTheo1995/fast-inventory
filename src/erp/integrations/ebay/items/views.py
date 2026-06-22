from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from src.erp.integrations.ebay.items.dependencies import get_ebay_service
from src.erp.integrations.ebay.items.schemas import EbayCreateItem, EbayItem, EbayItemResponse
from src.erp.integrations.ebay.items.service import EbayItemService

router = APIRouter()


@router.get("", response_model=list[EbayItem], status_code=status.HTTP_200_OK)
def get_items(service: Annotated[EbayItemService, Depends(get_ebay_service)]) -> list[EbayItem]:
    """
    Fetch eBay items (via ERP mapping layer)
    """
    return service.get_items()


@router.post("/", response_model=EbayItemResponse, status_code=status.HTTP_201_CREATED)
def create_item(
    item_in: EbayCreateItem, service: Annotated[EbayItemService, Depends(get_ebay_service)]
) -> EbayItemResponse:
    """
    Creates a new eBay item record in the ERP (not on eBay).
    """
    item = service.create_item(item_in)

    if not item:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create ERP(eBay) item. Please verify the provided data.",
        )

    return item


@router.post("/sync", response_model=list[EbayItem], status_code=status.HTTP_200_OK)
def sync_items(service: Annotated[EbayItemService, Depends(get_ebay_service)]) -> list[EbayItem]:
    """
    Trigger manual sync from eBay
    (useful for FE button or cron jobs)
    """
    return service.sync_items()
