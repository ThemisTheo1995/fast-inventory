from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.erp.api.pricing.schemas import WorkspaceUsageResponse
from src.erp.api.pricing.service import PricingUsageService
from src.erp.database.base import get_db

router = APIRouter()


@router.get("/{workspace_id}/usage", response_model=WorkspaceUsageResponse, status_code=status.HTTP_200_OK)
def workspace_usage(workspace_id: UUID, db: Annotated[Session, Depends(get_db)]) -> WorkspaceUsageResponse:

    service = PricingUsageService(db)

    return service.get_workspace_usage(workspace_id)
