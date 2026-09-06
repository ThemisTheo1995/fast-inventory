from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from erp.api.pricing.schemas import WorkspaceUsageResponse
from erp.api.pricing.service import PricingUsageService
from erp.database.base import get_db

router = APIRouter()


@router.get("/{workspace_id}/usage", response_model=WorkspaceUsageResponse, status_code=status.HTTP_200_OK)
async def workspace_usage(workspace_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]) -> WorkspaceUsageResponse:

    service = PricingUsageService(db)

    return await service.get_workspace_usage(workspace_id)
