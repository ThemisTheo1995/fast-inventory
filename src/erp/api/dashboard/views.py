from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.erp.api.dashboard.schemas import DashboardResponse
from src.erp.api.dashboard.service import DashboardService
from src.erp.database.base import get_db

router = APIRouter()


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    workspace_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DashboardResponse:

    service = DashboardService(db)

    return await service.get_full_dashboard(workspace_id)
