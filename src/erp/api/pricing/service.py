from datetime import datetime
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.erp.api.pricing.enums import MetricType
from src.erp.api.pricing.models import PricingPlan, PricingUsage
from src.erp.api.pricing.schemas import (
    MetricTypeUsage,
    PlanNameUsage,
    PricingUsageCreate,
    WorkspaceUsageResponse,
)
from src.erp.core.utils import get_end_of_month, get_start_of_month


class PricingUsageService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_workspace_usage(
        self,
        workspace_id: UUID,
        start_dt: datetime | None = None,
        end_dt: datetime | None = None,
    ) -> WorkspaceUsageResponse:

        if start_dt is None or end_dt is None:
            start_dt = get_start_of_month()
            end_dt = get_end_of_month()

        results = (
            self.db.query(
                PricingPlan.name.label("plan_name"),
                PricingUsage.metric_type,
                func.count(PricingUsage.id).label("used"),
                PricingPlan.api_limit,
                PricingPlan.listings_limit,
            )
            .join(PricingPlan, PricingUsage.plan_id == PricingPlan.id)
            .filter(
                PricingUsage.workspace_id == workspace_id,
                PricingUsage.created_at >= start_dt,
                PricingUsage.created_at <= end_dt,
            )
            .group_by(PricingPlan.name, PricingUsage.metric_type, PricingPlan.api_limit, PricingPlan.listings_limit)
            .all()
        )

        plans_data = {}

        for row in results:
            if row.plan_name not in plans_data:
                plans_data[row.plan_name] = PlanNameUsage(metrics={})

            limit = row.api_limit if row.metric_type == MetricType.API_REQUEST else row.listings_limit

            plans_data[row.plan_name].metrics[row.metric_type.value] = MetricTypeUsage(used=row.used, total=limit)

        return WorkspaceUsageResponse(workspace_id=workspace_id, plans=plans_data)

    def add_usage(self, data: PricingUsageCreate) -> None:

        new_event = PricingUsage(
            workspace_id=data.workspace_id,
            plan_id=data.plan_id,
            metric_type=data.metric_name,
            request_type=data.http_method,
        )

        self.db.add(new_event)
        self.db.commit()
