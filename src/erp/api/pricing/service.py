from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from erp.api.pricing.enums import MetricType, PlanName
from erp.api.pricing.models import PricingPlan, PricingUsage
from erp.api.pricing.schemas import (
    MetricTypeUsage,
    PlanLimitsResponse,
    PlanNameUsage,
    PricingPlanResponse,
    PricingUsageCreate,
    WorkspaceUsageResponse,
)
from erp.core.utils import get_end_of_month, get_start_of_month

if TYPE_CHECKING:
    from collections.abc import Sequence

PLAN_METADATA: dict[PlanName, dict[str, Any]] = {
    PlanName.GROWTH: {
        "display_name": "Growth",
        "tagline": "Ideal for establishing side channels.",
        "icon": "Store",
        "features": [
            "Standard automated sync rates",
            "Email customer support response",
            "Basic system analytics dashboards",
        ],
    },
    PlanName.PRO: {
        "display_name": "Pro",
        "tagline": "Optimized for high-velocity merchants.",
        "icon": "Zap",
        "features": [
            "Priority real-time instant webhooks",
            "Dedicated 24/7 priority live support",
            "Advanced financial ledger reports",
            "Multi-currency processing matrices",
        ],
    },
    PlanName.ENTERPRISE: {
        "display_name": "Enterprise",
        "tagline": "Built for high-volume operations.",
        "icon": "Sparkles",
        "features": [
            "Custom tailored ingestion API endpoints",
            "Personal account success engineer",
            "SLA performance uptime guarantee",
            "Custom white-label store reporting panels",
        ],
    },
    PlanName.CUSTOM: {
        "display_name": "Custom",
        "tagline": "For high-volume global storefronts.",
        "icon": "Headphones",
        "features": [
            "Dedicated backend infrastructure configuration",
            "Custom sync clock parameters (down to 1 min)",
            "Bespoke legal contracts & data NDAs",
            "Direct developer Slack channel sync",
        ],
    },
}


class PricingUsageService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_workspace_usage(
        self,
        workspace_id: UUID,
        start_dt: datetime | None = None,
        end_dt: datetime | None = None,
    ) -> WorkspaceUsageResponse:

        if start_dt is None or end_dt is None:
            start_dt = get_start_of_month()
            end_dt = get_end_of_month()

        stmt = (
            select(
                PricingPlan.name.label("plan_name"),
                PricingUsage.metric_type,
                func.count(PricingUsage.id).label("used"),
                PricingPlan.api_limit,
                PricingPlan.listings_limit,
            )
            .join(PricingPlan, PricingUsage.plan_id == PricingPlan.id)
            .where(
                PricingUsage.workspace_id == workspace_id,
                PricingUsage.created_at >= start_dt,
                PricingUsage.created_at <= end_dt,
            )
            .group_by(PricingPlan.name, PricingUsage.metric_type, PricingPlan.api_limit, PricingPlan.listings_limit)
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        plans_data = {}

        for row in rows:
            if row.plan_name not in plans_data:
                plans_data[row.plan_name] = PlanNameUsage(metrics={})

            limit = row.api_limit if row.metric_type == MetricType.API_REQUEST else row.listings_limit

            plans_data[row.plan_name].metrics[row.metric_type.value] = MetricTypeUsage(used=row.used, total=limit)

        return WorkspaceUsageResponse(workspace_id=workspace_id, plans=plans_data)

    async def add_usage(self, data: PricingUsageCreate) -> None:

        new_event = PricingUsage(
            workspace_id=data.workspace_id,
            plan_id=data.plan_id,
            metric_type=data.metric_name,
            request_type=data.http_method,
            user_id=data.user_id,
        )

        self.db.add(new_event)
        await self.db.commit()


class PricingPlanService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_available_plans(self) -> list[PricingPlanResponse]:
        stmt = select(PricingPlan).order_by(PricingPlan.price_monthly.asc())
        result = await self.db.execute(stmt)
        plans: Sequence[PricingPlan] = result.scalars().all()

        response_plans: list[PricingPlanResponse] = []

        for plan in plans:
            meta = PLAN_METADATA.get(
                plan.name,
                {
                    "display_name": str(plan.name.value).title(),
                    "tagline": "",
                    "icon": "Store",
                    "features": [],
                },
            )

            price_val: int | str = "Custom" if plan.price_monthly <= 0 else plan.price_monthly

            response_plans.append(
                PricingPlanResponse(
                    id=plan.id,
                    name=meta["display_name"],
                    tagline=meta["tagline"],
                    price=price_val,
                    icon=meta["icon"],
                    limits=PlanLimitsResponse(
                        listings=f"{plan.listings_limit:,}",
                        api=f"{plan.api_limit:,}",
                    ),
                    features=meta["features"],
                )
            )

        return response_plans
