import uuid

import pytest
from sqlalchemy.orm import Session

from src.erp.api.pricing.enums import PlanName
from src.erp.api.pricing.models import PricingPlan
from src.erp.api.pricing.service import PricingUsageService


@pytest.fixture
def service(db_session: Session) -> PricingUsageService:
    """Provides a fresh PricingUsageService instance."""
    return PricingUsageService(db=db_session)


@pytest.fixture
def enterprise_plan(db_session: Session) -> PricingPlan:
    """Seeds an additional pricing plan to test multi-plan reporting per workspace."""
    plan = PricingPlan(
        id=uuid.uuid4(),
        name=PlanName.ENTERPRISE,
        api_limit=10000,
        listings_limit=500,
        price_monthly=9999,
    )
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)
    return plan
