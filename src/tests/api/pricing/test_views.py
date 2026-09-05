from datetime import UTC, datetime

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from src.erp.api.pricing.enums import HttpMethod, MetricType
from src.erp.api.pricing.models import PricingUsage


async def test_router_get_workspace_usage_empty(client, seed_workspace):
    """Verifies fetching usage for a workspace with no usage records returns an empty plans payload."""
    response = await client.get(f"/{seed_workspace}/usage")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["workspace_id"] == str(seed_workspace)
    assert data["plans"] == {}


async def test_router_get_workspace_usage_success(client, db_session: AsyncSession, seed_workspace, pricing_plan):
    """Verifies retrieval of aggregated usage metrics for a specific workspace."""
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

    response = await client.get(f"/{seed_workspace}/usage")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["workspace_id"] == str(seed_workspace)
    assert pricing_plan.name in data["plans"]

    metrics = data["plans"][pricing_plan.name]["metrics"]
    assert metrics[MetricType.API_REQUEST.value]["used"] == 1
    assert metrics[MetricType.API_REQUEST.value]["total"] == pricing_plan.api_limit
    assert metrics[MetricType.LISTING.value]["used"] == 1
    assert metrics[MetricType.LISTING.value]["total"] == pricing_plan.listings_limit


async def test_router_get_workspace_usage_isolation(
    client, db_session: AsyncSession, seed_workspace, alt_workspace, pricing_plan
):
    """Verifies usage metrics are isolated to the requested workspace route parameter."""
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
                request_type=HttpMethod.POST,
                created_at=now,
            ),
        ]
    )
    await db_session.commit()

    response = await client.get(f"/{seed_workspace}/usage")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["workspace_id"] == str(seed_workspace)
    plan_data = data["plans"][pricing_plan.name]
    assert plan_data["metrics"][MetricType.API_REQUEST.value]["used"] == 1


async def test_router_get_workspace_usage_invalid_workspace_id(client):
    """Verifies fetching workspace usage with an invalid UUID format returns 422 UNPROCESSABLE CONTENT."""
    invalid_uuid = "not-a-valid-uuid"

    response = await client.get(f"/{invalid_uuid}/usage")

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
