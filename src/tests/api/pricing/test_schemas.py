import uuid

import pytest
from pydantic import ValidationError

from erp.api.pricing.enums import HttpMethod, MetricType, PlanName
from erp.api.pricing.schemas import (
    MetricTypeUsage,
    PlanNameUsage,
    PricingUsageCreate,
    WorkspaceUsageResponse,
)

# ============================================================================
# PricingUsageCreate Tests
# ============================================================================


def test_pricing_usage_create_valid_with_enums():
    """Verifies creation using explicit Enum instances."""
    workspace_id = uuid.uuid4()
    plan_id = uuid.uuid4()

    schema = PricingUsageCreate(
        workspace_id=workspace_id,
        plan_id=plan_id,
        metric_name=MetricType.API_REQUEST,
        http_method=HttpMethod.POST,
    )

    assert schema.workspace_id == workspace_id
    assert schema.plan_id == plan_id
    assert schema.metric_name == MetricType.API_REQUEST
    assert schema.http_method == HttpMethod.POST


@pytest.mark.parametrize(
    "metric_input, method_input",
    [
        (MetricType.LISTING, HttpMethod.GET),
        ("listing", "GET"),
        ("api_request", "POST"),
    ],
)
def test_pricing_usage_create_accepts_enum_and_string_values(metric_input, method_input):
    """Verifies Pydantic validates both Enum instances and equivalent raw string values."""
    schema = PricingUsageCreate(
        workspace_id=uuid.uuid4(),
        plan_id=uuid.uuid4(),
        metric_name=metric_input,
        http_method=method_input,
    )

    assert schema.metric_name == metric_input
    assert schema.http_method == method_input


@pytest.mark.parametrize(
    "field_name",
    ["workspace_id", "plan_id", "metric_name", "http_method"],
)
def test_pricing_usage_create_missing_required_fields(field_name):
    """Verifies validation failure when any required field is missing."""
    data = {
        "workspace_id": uuid.uuid4(),
        "plan_id": uuid.uuid4(),
        "metric_name": MetricType.API_REQUEST,
        "http_method": HttpMethod.GET,
    }
    del data[field_name]

    with pytest.raises(ValidationError) as exc_info:
        PricingUsageCreate(**data)

    errors = exc_info.value.errors()
    assert any(err["loc"][0] == field_name for err in errors)


def test_pricing_usage_create_invalid_enum_values():
    """Verifies failure when passing unsupported enum strings."""
    with pytest.raises(ValidationError) as exc_info:
        PricingUsageCreate(
            workspace_id=uuid.uuid4(),
            plan_id=uuid.uuid4(),
            metric_name="INVALID_METRIC",
            http_method="OPTIONS",
        )

    errors = exc_info.value.errors()
    failed_fields = [err["loc"][0] for err in errors]
    assert "metric_name" in failed_fields
    assert "http_method" in failed_fields


def test_pricing_usage_create_invalid_uuid():
    """Verifies failure when passing invalid UUID formats."""
    with pytest.raises(ValidationError) as exc_info:
        PricingUsageCreate(
            workspace_id="invalid-uuid-string",
            plan_id=uuid.uuid4(),
            metric_name=MetricType.API_REQUEST,
            http_method=HttpMethod.POST,
        )

    assert exc_info.value.errors()[0]["loc"][0] == "workspace_id"


# ============================================================================
# MetricTypeUsage Tests
# ============================================================================


def test_metric_type_usage_valid():
    """Verifies successful instantiation of integer usage counts."""
    schema = MetricTypeUsage(used=150, total=1000)

    assert schema.used == 150
    assert schema.total == 1000


@pytest.mark.parametrize(
    "invalid_data, expected_error_field",
    [
        ({"used": "not_an_int", "total": 100}, "used"),
        ({"used": 50, "total": "not_an_int"}, "total"),
        ({"used": 50}, "total"),
    ],
)
def test_metric_type_usage_invalid(invalid_data, expected_error_field):
    """Verifies validation failure for non-integer counts or missing fields."""
    with pytest.raises(ValidationError) as exc_info:
        MetricTypeUsage(**invalid_data)

    assert any(err["loc"][0] == expected_error_field for err in exc_info.value.errors())


# ============================================================================
# PlanNameUsage Tests
# ============================================================================


def test_plan_name_usage_valid_with_metric_type_keys():
    """Verifies metrics dictionary using MetricType values as keys."""
    data = {
        "metrics": {
            MetricType.API_REQUEST: {"used": 250, "total": 1000},
            MetricType.LISTING: MetricTypeUsage(used=50, total=200),
        }
    }
    schema = PlanNameUsage(**data)

    assert schema.metrics[MetricType.API_REQUEST].used == 250
    assert schema.metrics[MetricType.LISTING].total == 200


def test_plan_name_usage_invalid_nested():
    """Verifies nested error propagation when MetricTypeUsage fails validation."""
    data = {
        "metrics": {
            MetricType.API_REQUEST: {"used": "invalid", "total": 1000},
        }
    }
    with pytest.raises(ValidationError) as exc_info:
        PlanNameUsage(**data)

    errors = exc_info.value.errors()
    assert errors[0]["loc"] == ("metrics", MetricType.API_REQUEST.value, "used")


# ============================================================================
# WorkspaceUsageResponse Tests
# ============================================================================


def test_workspace_usage_response_valid_with_plan_name_keys():
    """Verifies full response schema utilizing PlanName and MetricType enums."""
    workspace_id = uuid.uuid4()
    data = {
        "workspace_id": workspace_id,
        "plans": {
            PlanName.PRO: {
                "metrics": {
                    MetricType.API_REQUEST: {"used": 4500, "total": 10000},
                    MetricType.LISTING: {"used": 12, "total": 50},
                }
            },
            PlanName.ENTERPRISE: {
                "metrics": {
                    MetricType.API_REQUEST: {"used": 0, "total": 100000},
                }
            },
        },
    }
    schema = WorkspaceUsageResponse(**data)

    assert schema.workspace_id == workspace_id
    assert PlanName.PRO in schema.plans
    assert schema.plans[PlanName.PRO].metrics[MetricType.API_REQUEST].used == 4500
    assert schema.plans[PlanName.ENTERPRISE].metrics[MetricType.API_REQUEST].total == 100000


def test_workspace_usage_response_invalid_workspace_id():
    """Verifies validation error on invalid UUID."""
    with pytest.raises(ValidationError) as exc_info:
        WorkspaceUsageResponse(
            workspace_id="not-a-valid-uuid",
            plans={},
        )

    assert exc_info.value.errors()[0]["loc"][0] == "workspace_id"
