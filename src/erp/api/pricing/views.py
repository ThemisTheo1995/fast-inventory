from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from erp.api.auth.permissions import verify_workspace_access
from erp.api.pricing.schemas import PricingPlanResponse, WorkspaceUsageResponse
from erp.api.pricing.service import PricingPlanService, PricingUsageService
from erp.api.workspace_user.models import WorkspaceUser
from erp.database.base import get_db

router = APIRouter()


@router.get("/plans", response_model=list[PricingPlanResponse], status_code=status.HTTP_200_OK)
async def get_plans(db: Annotated[AsyncSession, Depends(get_db)]) -> list[PricingPlanResponse]:
    """
    Public endpoint to retrieve all available billing subscription tiers.
    """
    service = PricingPlanService(db)
    return await service.get_available_plans()


@router.get("/{workspace_id}/usage", response_model=WorkspaceUsageResponse, status_code=status.HTTP_200_OK)
async def workspace_usage(
    workspace_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _workspace_access: Annotated[WorkspaceUser, Depends(verify_workspace_access)],
) -> WorkspaceUsageResponse:

    service = PricingUsageService(db)

    return await service.get_workspace_usage(workspace_id)
