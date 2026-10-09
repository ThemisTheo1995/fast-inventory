from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from erp.api.pricing.enums import HttpMethod, MetricType


class PricingUsageCreate(BaseModel):
    workspace_id: UUID
    plan_id: UUID
    user_id: UUID
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


class PlanLimitsResponse(BaseModel):
    listings: str
    api: str


class PricingPlanResponse(BaseModel):
    id: UUID | str
    name: str
    tagline: str
    price: int | str = Field(..., description="Monthly price or 'Custom'")
    icon: str
    limits: PlanLimitsResponse
    features: list[str]

    model_config = ConfigDict(from_attributes=True)
