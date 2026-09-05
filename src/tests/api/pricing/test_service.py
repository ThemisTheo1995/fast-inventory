import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.erp.api.pricing.enums import HttpMethod, MetricType
from src.erp.api.pricing.models import PricingPlan, PricingUsage
from src.erp.api.pricing.schemas import PricingUsageCreate, WorkspaceUsageResponse
from src.erp.api.pricing.service import PricingUsageService
from src.erp.core.utils import get_start_of_month

# ============================================================================
# add_usage Tests
# ============================================================================


@pytest.mark.parametrize(
    "metric_type, http_method",
    [
        (MetricType.API_REQUEST, HttpMethod.GET),
        (MetricType.API_REQUEST, HttpMethod.POST),
        (MetricType.LISTING, HttpMethod.PUT),
        (MetricType.LISTING, HttpMethod.DELETE),
    ],
)
async def test_add_usage_success(
    db_session: AsyncSession,
    service: PricingUsageService,
    seed_workspace: uuid.UUID,
    pricing_plan: PricingPlan,
    metric_type: MetricType,
    http_method: HttpMethod,
):
    """Verifies add_usage successfully records usage using global workspace and plan fixtures."""
    usage_data = PricingUsageCreate(
        workspace_id=seed_workspace,
        plan_id=pricing_plan.id,
        metric_name=metric_type,
        http_method=http_method,
    )

    await service.add_usage(usage_data)

    result = await db_session.execute(select(PricingUsage).where(PricingUsage.workspace_id == seed_workspace))
    record = result.scalars().first()

    assert record is not None
    assert record.workspace_id == seed_workspace
    assert record.plan_id == pricing_plan.id
    assert record.metric_type == metric_type
    assert record.request_type == http_method


# ============================================================================
# get_workspace_usage Tests
# ============================================================================


async def test_get_workspace_usage_empty_state(service: PricingUsageService, seed_workspace: uuid.UUID):
    """Verifies get_workspace_usage returns an empty plans dict when no usage events exist."""
    response = await service.get_workspace_usage(workspace_id=seed_workspace)

    assert isinstance(response, WorkspaceUsageResponse)
    assert response.workspace_id == seed_workspace
    assert response.plans == {}


async def test_get_workspace_usage_metric_limit_routing(
    db_session: AsyncSession,
    service: PricingUsageService,
    seed_workspace: uuid.UUID,
    pricing_plan: PricingPlan,
):
    """Verifies API_REQUEST routes to api_limit and LISTING routes to listings_limit."""
    now = datetime.now(UTC)

    db_session.add_all(
        [
            PricingUsage(
                workspace_id=seed_workspace,
                plan_id=pricing_plan.id,
                metric_type=MetricType.API_REQUEST,
                request_type=HttpMethod.GET,
                created_at=now,
            ),
            PricingUsage(
                workspace_id=seed_workspace,
                plan_id=pricing_plan.id,
                metric_type=MetricType.LISTING,
                request_type=HttpMethod.POST,
                created_at=now,
            ),
        ]
    )
    await db_session.commit()

    response = await service.get_workspace_usage(workspace_id=seed_workspace)
    plan_metrics = response.plans[pricing_plan.name].metrics

    # API_REQUEST -> pricing_plan.api_limit
    assert plan_metrics[MetricType.API_REQUEST.value].used == 1
    assert plan_metrics[MetricType.API_REQUEST.value].total == pricing_plan.api_limit

    # LISTING -> pricing_plan.listings_limit
    assert plan_metrics[MetricType.LISTING.value].used == 1
    assert plan_metrics[MetricType.LISTING.value].total == pricing_plan.listings_limit


async def test_get_workspace_usage_http_method_aggregation(
    db_session: AsyncSession,
    service: PricingUsageService,
    seed_workspace: uuid.UUID,
    pricing_plan: PricingPlan,
):
    """Verifies distinct HTTP verbs for the same metric type aggregate into a single metric count."""
    now = datetime.now(UTC)

    db_session.add_all(
        [
            PricingUsage(
                workspace_id=seed_workspace,
                plan_id=pricing_plan.id,
                metric_type=MetricType.API_REQUEST,
                request_type=HttpMethod.GET,
                created_at=now,
            ),
            PricingUsage(
                workspace_id=seed_workspace,
                plan_id=pricing_plan.id,
                metric_type=MetricType.API_REQUEST,
                request_type=HttpMethod.POST,
                created_at=now,
            ),
            PricingUsage(
                workspace_id=seed_workspace,
                plan_id=pricing_plan.id,
                metric_type=MetricType.API_REQUEST,
                request_type=HttpMethod.DELETE,
                created_at=now,
            ),
        ]
    )
    await db_session.commit()

    response = await service.get_workspace_usage(workspace_id=seed_workspace)
    api_metric = response.plans[pricing_plan.name].metrics[MetricType.API_REQUEST.value]

    assert api_metric.used == 3


async def test_get_workspace_usage_multiple_plans(
    db_session: AsyncSession,
    service: PricingUsageService,
    seed_workspace: uuid.UUID,
    pricing_plan: PricingPlan,
    enterprise_plan: PricingPlan,
):
    """Verifies that usage under different plans is segregated correctly by plan_name."""
    now = datetime.now(UTC)

    db_session.add_all(
        [
            PricingUsage(
                workspace_id=seed_workspace,
                plan_id=pricing_plan.id,
                metric_type=MetricType.API_REQUEST,
                request_type=HttpMethod.GET,
                created_at=now,
            ),
            PricingUsage(
                workspace_id=seed_workspace,
                plan_id=enterprise_plan.id,
                metric_type=MetricType.API_REQUEST,
                request_type=HttpMethod.GET,
                created_at=now,
            ),
        ]
    )
    await db_session.commit()

    response = await service.get_workspace_usage(workspace_id=seed_workspace)

    assert pricing_plan.name in response.plans
    assert enterprise_plan.name in response.plans
    assert response.plans[pricing_plan.name].metrics[MetricType.API_REQUEST.value].total == pricing_plan.api_limit
    assert response.plans[enterprise_plan.name].metrics[MetricType.API_REQUEST.value].total == enterprise_plan.api_limit


async def test_get_workspace_usage_exact_date_boundaries(
    db_session: AsyncSession,
    service: PricingUsageService,
    seed_workspace: uuid.UUID,
    pricing_plan: PricingPlan,
):
    """Verifies inclusive boundary filtering (>= start_dt and <= end_dt)."""
    start_dt = datetime(2026, 3, 10, 0, 0, 0, tzinfo=UTC)
    end_dt = datetime(2026, 3, 20, 23, 59, 59, tzinfo=UTC)

    db_session.add_all(
        [
            # Exactly on start_dt (Included)
            PricingUsage(
                workspace_id=seed_workspace,
                plan_id=pricing_plan.id,
                metric_type=MetricType.API_REQUEST,
                request_type=HttpMethod.GET,
                created_at=start_dt,
            ),
            # Exactly on end_dt (Included)
            PricingUsage(
                workspace_id=seed_workspace,
                plan_id=pricing_plan.id,
                metric_type=MetricType.API_REQUEST,
                request_type=HttpMethod.GET,
                created_at=end_dt,
            ),
            # 1 second before start_dt (Excluded)
            PricingUsage(
                workspace_id=seed_workspace,
                plan_id=pricing_plan.id,
                metric_type=MetricType.API_REQUEST,
                request_type=HttpMethod.GET,
                created_at=start_dt - timedelta(seconds=1),
            ),
            # 1 second after end_dt (Excluded)
            PricingUsage(
                workspace_id=seed_workspace,
                plan_id=pricing_plan.id,
                metric_type=MetricType.API_REQUEST,
                request_type=HttpMethod.GET,
                created_at=end_dt + timedelta(seconds=1),
            ),
        ]
    )
    await db_session.commit()

    response = await service.get_workspace_usage(
        workspace_id=seed_workspace,
        start_dt=start_dt,
        end_dt=end_dt,
    )

    api_metric = response.plans[pricing_plan.name].metrics[MetricType.API_REQUEST.value]
    assert api_metric.used == 2


@pytest.mark.parametrize(
    "start_dt_arg, end_dt_arg",
    [
        (None, None),
        (datetime(2026, 1, 1, tzinfo=UTC), None),
        (None, datetime(2026, 1, 31, tzinfo=UTC)),
    ],
)
async def test_get_workspace_usage_partial_or_missing_dates_triggers_default_month(
    db_session: AsyncSession,
    service: PricingUsageService,
    seed_workspace: uuid.UUID,
    pricing_plan: PricingPlan,
    start_dt_arg: datetime | None,
    end_dt_arg: datetime | None,
):
    """Verifies that if either date parameter is None, current month start/end defaults are used."""
    start_of_month = get_start_of_month()

    db_session.add_all(
        [
            PricingUsage(
                workspace_id=seed_workspace,
                plan_id=pricing_plan.id,
                metric_type=MetricType.API_REQUEST,
                request_type=HttpMethod.GET,
                created_at=start_of_month + timedelta(days=2),
            ),
            PricingUsage(
                workspace_id=seed_workspace,
                plan_id=pricing_plan.id,
                metric_type=MetricType.API_REQUEST,
                request_type=HttpMethod.GET,
                created_at=start_of_month - timedelta(days=2),
            ),
        ]
    )
    await db_session.commit()

    response = await service.get_workspace_usage(
        workspace_id=seed_workspace,
        start_dt=start_dt_arg,
        end_dt=end_dt_arg,
    )

    api_metric = response.plans[pricing_plan.name].metrics[MetricType.API_REQUEST.value]
    assert api_metric.used == 1


async def test_get_workspace_usage_workspace_isolation(
    db_session: AsyncSession,
    service: PricingUsageService,
    seed_workspace: uuid.UUID,
    alt_workspace: uuid.UUID,
    pricing_plan: PricingPlan,
):
    """Verifies workspace isolation using seed_workspace and alt_workspace fixtures."""
    now = datetime.now(UTC)

    db_session.add_all(
        [
            PricingUsage(
                workspace_id=seed_workspace,
                plan_id=pricing_plan.id,
                metric_type=MetricType.API_REQUEST,
                request_type=HttpMethod.GET,
                created_at=now,
            ),
            PricingUsage(
                workspace_id=alt_workspace,
                plan_id=pricing_plan.id,
                metric_type=MetricType.API_REQUEST,
                request_type=HttpMethod.GET,
                created_at=now,
            ),
        ]
    )
    await db_session.commit()

    response = await service.get_workspace_usage(workspace_id=seed_workspace)

    assert response.workspace_id == seed_workspace
    assert response.plans[pricing_plan.name].metrics[MetricType.API_REQUEST.value].used == 1
