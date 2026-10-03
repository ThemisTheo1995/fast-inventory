import pytest

from erp.api.pricing.enums import HttpMethod, MetricType, PlanName

# ============================================================================
# PlanName Enum Tests
# ============================================================================


def test_plan_name_values():
    """Verifies PlanName members match expected string values."""
    assert PlanName.GROWTH == "growth"
    assert PlanName.PRO == "pro"
    assert PlanName.ENTERPRISE == "enterprise"
    assert PlanName.CUSTOM == "custom"


@pytest.mark.parametrize(
    "val, expected_enum",
    [
        ("growth", PlanName.GROWTH),
        ("pro", PlanName.PRO),
        ("enterprise", PlanName.ENTERPRISE),
        ("custom", PlanName.CUSTOM),
    ],
)
def test_plan_name_valid_instantiation(val: str, expected_enum: PlanName):
    """Verifies PlanName can be constructed from string values."""
    assert PlanName(val) is expected_enum
    assert isinstance(PlanName(val), str)


def test_plan_name_invalid_value_raises_value_error():
    """Verifies passing an unknown plan name string raises ValueError."""
    with pytest.raises(ValueError):
        PlanName("unsupported_plan")


# ============================================================================
# MetricType Enum Tests (auto() behavior)
# ============================================================================


def test_metric_type_auto_lowercased_values():
    """Verifies MetricType auto() correctly generates lowercased string values."""
    assert MetricType.API_REQUEST == "api_request"
    assert MetricType.LISTING == "listing"


@pytest.mark.parametrize(
    "val, expected_enum",
    [
        ("api_request", MetricType.API_REQUEST),
        ("listing", MetricType.LISTING),
    ],
)
def test_metric_type_valid_instantiation(val: str, expected_enum: MetricType):
    """Verifies MetricType can be constructed from lowercased string values."""
    assert MetricType(val) is expected_enum


def test_metric_type_invalid_value_raises_value_error():
    """Verifies passing an invalid metric string raises ValueError."""
    with pytest.raises(ValueError):
        MetricType("DATABASE_READ")


# ============================================================================
# HttpMethod Enum Tests
# ============================================================================


def test_http_method_values():
    """Verifies HttpMethod members match expected upper-case HTTP verbs."""
    assert HttpMethod.GET == "GET"
    assert HttpMethod.POST == "POST"
    assert HttpMethod.PUT == "PUT"
    assert HttpMethod.PATCH == "PATCH"
    assert HttpMethod.DELETE == "DELETE"


@pytest.mark.parametrize(
    "verb, expected_enum",
    [
        ("GET", HttpMethod.GET),
        ("POST", HttpMethod.POST),
        ("PUT", HttpMethod.PUT),
        ("PATCH", HttpMethod.PATCH),
        ("DELETE", HttpMethod.DELETE),
    ],
)
def test_http_method_valid_instantiation(verb: str, expected_enum: HttpMethod):
    """Verifies HttpMethod can be constructed from HTTP verb strings."""
    assert HttpMethod(verb) is expected_enum


def test_http_method_invalid_value_raises_value_error():
    """Verifies lowercased or unsupported HTTP verbs raise ValueError."""
    with pytest.raises(ValueError):
        HttpMethod("get")  # Case-sensitive check

    with pytest.raises(ValueError):
        HttpMethod("CONNECT")
