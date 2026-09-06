import uuid

from sqlalchemy import Boolean, Enum as SQLAlchemyEnum, ForeignKey, Index, Integer, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from erp.api.base.models import BaseModel
from erp.api.pricing.enums import HttpMethod, MetricType, PlanName


class PricingPlan(BaseModel):
    __tablename__ = "pricing_plans"

    name: Mapped[PlanName] = mapped_column(
        SQLAlchemyEnum(
            PlanName,
            native_enum=False,
            length=50,
        ),
        default=PlanName.GROWTH,
    )
    listings_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    api_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    price_monthly: Mapped[int] = mapped_column(Integer, nullable=False)

    subscriptions: Mapped[list["PricingSubscription"]] = relationship(back_populates="plan")


class PricingSubscription(BaseModel):
    __tablename__ = "pricing_subscriptions"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pricing_plans.id"), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_paused: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    plan: Mapped["PricingPlan"] = relationship(back_populates="subscriptions")

    __table_args__ = (
        Index(
            "uq_active_subscription_per_workspace",
            "workspace_id",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
    )


class PricingUsage(BaseModel):
    __tablename__ = "pricing_usage"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pricing_plans.id"), nullable=False)

    metric_type: Mapped[MetricType] = mapped_column(SQLAlchemyEnum(MetricType), nullable=False)
    request_type: Mapped[HttpMethod] = mapped_column(SQLAlchemyEnum(HttpMethod), nullable=False)

    __table_args__ = (Index("ix_usage_workspace_plan_date", "workspace_id", "plan_id", "created_at"),)
