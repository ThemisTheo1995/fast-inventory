import uuid

from sqlalchemy import Enum as SQLAlchemyEnum, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.erp.api.base.models import BaseModel
from src.erp.api.pricing.enums import PlanName


class PricingPlan(BaseModel):
    __tablename__ = "pricing_plans"

    name: Mapped[PlanName] = mapped_column(SQLAlchemyEnum(PlanName), nullable=False)
    listings_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    api_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    price_monthly: Mapped[int] = mapped_column(Integer, nullable=False)

    subscriptions: Mapped[list["PricingSubscription"]] = relationship(back_populates="plan")


class PricingSubscription(BaseModel):
    __tablename__ = "pricing_subscriptions"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pricing_plans.id"), nullable=False)

    plan: Mapped["PricingPlan"] = relationship(back_populates="subscriptions")


class PricingUsage(BaseModel):
    __tablename__ = "pricing_usage"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False, index=True)
    listings_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    api_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
