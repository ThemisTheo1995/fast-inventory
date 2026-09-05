from typing import Annotated

from fastapi import BackgroundTasks, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.erp.api.pricing.enums import HttpMethod, MetricType
from src.erp.api.pricing.schemas import PricingUsageCreate
from src.erp.api.pricing.service import PricingUsageService
from src.erp.database.base import get_db


async def log_usage(
    request: Request, background_tasks: BackgroundTasks, db: Annotated[AsyncSession, Depends(get_db)]
) -> None:

    metric_name = MetricType.API_REQUEST
    http_method = HttpMethod(request.method)

    data = PricingUsageCreate(
        workspace_id=request.state.workspace_user.workspace_id,
        plan_id=request.state.subscription_id,
        metric_name=metric_name,
        http_method=http_method,
    )

    background_tasks.add_task(PricingUsageService(db).add_usage, data)
