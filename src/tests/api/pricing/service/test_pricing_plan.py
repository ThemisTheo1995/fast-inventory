from enum import Enum
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from erp.api.pricing.enums import PlanName
from erp.api.pricing.service import PLAN_METADATA, PricingPlanService


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def service(mock_db):
    return PricingPlanService(mock_db)


def make_plan(name, price_monthly=100, listings_limit=500, api_limit=10000):
    return SimpleNamespace(
        id=uuid4(),
        name=name,
        price_monthly=price_monthly,
        listings_limit=listings_limit,
        api_limit=api_limit,
    )


@pytest.mark.asyncio
async def test_get_available_plans_returns_empty_list(service, mock_db):
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = result

    response = await service.get_available_plans()

    assert response == []


@pytest.mark.asyncio
@pytest.mark.parametrize("plan_name", list(PlanName))
async def test_get_available_plans_uses_plan_metadata(
    service,
    mock_db,
    plan_name,
):
    plan = make_plan(plan_name)

    result = MagicMock()
    result.scalars.return_value.all.return_value = [plan]
    mock_db.execute.return_value = result

    response = await service.get_available_plans()

    assert len(response) == 1

    response_plan = response[0]
    metadata = PLAN_METADATA[plan_name]

    assert response_plan.id == plan.id
    assert response_plan.name == metadata["display_name"]
    assert response_plan.tagline == metadata["tagline"]
    assert response_plan.icon == metadata["icon"]
    assert response_plan.features == metadata["features"]
    assert response_plan.price == plan.price_monthly
    assert response_plan.limits.listings == f"{plan.listings_limit:,}"
    assert response_plan.limits.api == f"{plan.api_limit:,}"


@pytest.mark.asyncio
@pytest.mark.parametrize("price", [0, -1, -100])
async def test_get_available_plans_returns_custom_for_nonpositive_price(
    service,
    mock_db,
    price,
):
    plan = make_plan(PlanName.GROWTH, price_monthly=price)

    result = MagicMock()
    result.scalars.return_value.all.return_value = [plan]
    mock_db.execute.return_value = result

    response = await service.get_available_plans()

    assert response[0].price == "Custom"


@pytest.mark.asyncio
@pytest.mark.usefixtures("service")
async def test_get_available_plans_returns_numeric_price_when_positive(
    mock_db,
):
    plan = make_plan(PlanName.PRO, price_monthly=199)

    result = MagicMock()
    result.scalars.return_value.all.return_value = [plan]
    mock_db.execute.return_value = result

    response = await PricingPlanService(mock_db).get_available_plans()

    assert response[0].price == 199


@pytest.mark.asyncio
async def test_get_available_plans_uses_fallback_metadata(
    service,
    mock_db,
):
    class UnknownPlan(Enum):
        UNKNOWN = "unknown"

    plan = make_plan(
        UnknownPlan.UNKNOWN,
        price_monthly=150,
        listings_limit=250,
        api_limit=5000,
    )

    result = MagicMock()
    result.scalars.return_value.all.return_value = [plan]
    mock_db.execute.return_value = result

    response = await service.get_available_plans()

    assert len(response) == 1

    response_plan = response[0]

    assert response_plan.id == plan.id
    assert response_plan.name == "Unknown"
    assert response_plan.tagline == ""
    assert response_plan.icon == "Store"
    assert response_plan.features == []
    assert response_plan.price == 150
    assert response_plan.limits.listings == "250"
    assert response_plan.limits.api == "5,000"


@pytest.mark.asyncio
async def test_get_available_plans_formats_large_limits(
    service,
    mock_db,
):
    plan = make_plan(
        PlanName.ENTERPRISE,
        listings_limit=1000000,
        api_limit=2500000,
    )

    result = MagicMock()
    result.scalars.return_value.all.return_value = [plan]
    mock_db.execute.return_value = result

    response = await service.get_available_plans()

    assert response[0].limits.listings == "1,000,000"
    assert response[0].limits.api == "2,500,000"


@pytest.mark.asyncio
async def test_get_available_plans_executes_query(service, mock_db):
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = result

    await service.get_available_plans()

    mock_db.execute.assert_awaited_once()
