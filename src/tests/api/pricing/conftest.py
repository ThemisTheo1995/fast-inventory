import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from src.erp.api.pricing.enums import PlanName
from src.erp.api.pricing.models import PricingPlan
from src.erp.api.pricing.service import PricingUsageService


@pytest.fixture
def service(db_session: AsyncSession) -> PricingUsageService:
    """Provides a fresh PricingUsageService instance."""
    return PricingUsageService(db=db_session)


@pytest_asyncio.fixture
async def enterprise_plan(db_session: AsyncSession) -> PricingPlan:
    """Seeds an additional pricing plan to test multi-plan reporting per workspace."""
    plan = PricingPlan(
        id=uuid.uuid4(),
        name=PlanName.ENTERPRISE,
        api_limit=10000,
        listings_limit=500,
        price_monthly=9999,
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)
    return plan
