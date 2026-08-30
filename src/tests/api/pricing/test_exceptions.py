from src.erp.api.pricing.exceptions import ActiveSubscriptionNotFoundError
from src.erp.core.exceptions import BaseAppError

# ============================================================================
# BaseAppError Exception Subclass Tests
# ============================================================================


def test_active_subscription_not_found_error():
    """Verifies ActiveSubscriptionNotFoundError initializes with 404 status code and expected detail."""
    err = ActiveSubscriptionNotFoundError()

    assert isinstance(err, BaseAppError)
    assert err.status_code == 404
    assert err.detail == "No active pricing plan found."
