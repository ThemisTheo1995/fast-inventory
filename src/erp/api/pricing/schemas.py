from uuid import UUID

from pydantic import BaseModel

from erp.api.pricing.enums import HttpMethod, MetricType


class PricingUsageCreate(BaseModel):
    workspace_id: UUID
    plan_id: UUID
    metric_name: MetricType
    http_method: HttpMethod


class MetricTypeUsage(BaseModel):
    used: int
    total: int


class PlanNameUsage(BaseModel):
    metrics: dict[str, MetricTypeUsage]


class WorkspaceUsageResponse(BaseModel):
    workspace_id: UUID
    plans: dict[str, PlanNameUsage]
