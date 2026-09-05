from unittest.mock import MagicMock

import pytest

from src.erp.api.auth.exceptions import InsufficientPermissionsError
from src.erp.api.auth.permissions import verify_workspace_access
from src.erp.api.pricing.exceptions import ActiveSubscriptionNotFoundError

# ==============================================================================
# DEPENDENCY TESTS: verify_workspace_access
# ==============================================================================


async def test_verify_workspace_access_no_subscription(db_session, seed_workspace, active_workspace_user):
    """
    Verifies that if a workspace has no active pricing subscription,
    access is immediately rejected with an ActiveSubscriptionNotFoundError.
    Note: We specifically DO NOT inject the `active_subscription` fixture here.
    """
    request = MagicMock()
    request.method = "GET"

    with pytest.raises(ActiveSubscriptionNotFoundError):
        await verify_workspace_access(
            request=request,
            workspace_id=seed_workspace,
            workspace_user=active_workspace_user,
            db=db_session,
        )


async def test_verify_workspace_access_success_state_injection(
    db_session, seed_workspace, active_workspace_user, active_subscription
):
    """
    Verifies the happy path: valid subscription, sufficient permissions.
    Ensures that the Request state is correctly hydrated with the user and plan_id.
    """
    request = MagicMock()
    request.method = "DELETE"  # active_workspace_user is FULL_ADMIN, so DELETE is allowed

    result = await verify_workspace_access(
        request=request,
        workspace_id=seed_workspace,
        workspace_user=active_workspace_user,
        db=db_session,
    )

    # 1. It returns the user
    assert result == active_workspace_user

    # 2. It injects the context into request.state
    assert request.state.workspace_user == active_workspace_user
    # Ensure it extracted the scalar plan_id, not the model object
    assert request.state.subscription_id == active_subscription.plan_id


@pytest.mark.parametrize(
    "method, role",
    [
        ("POST", "read_only"),  # POST requires 2, read_only is 1
        ("DELETE", "edit_only"),  # DELETE requires 3, edit_only is 2
        ("DELETE", "read_only"),  # DELETE requires 3, read_only is 1
        ("PUT", "read_only"),  # PUT requires 2, read_only is 1
        ("UNKNOWN", "edit_only"),  # Unknown method defaults to 3, edit_only is 2
        ("GET", "unknown"),  # GET requires 1, unknown role defaults to 0 (Fits VARCHAR(10))
    ],
)
async def test_verify_workspace_access_insufficient_permissions(
    method,
    role,
    db_session,
    seed_workspace,
    active_workspace_user,
    active_subscription,  # noqa
):
    """
    Verifies that any combination where the user's role weight is lower
    than the HTTP method's required weight correctly triggers a 403 Forbidden.
    """
    request = MagicMock()
    request.method = method

    # Temporarily downgrade the active user's role for this test
    active_workspace_user.role = role

    with pytest.raises(InsufficientPermissionsError):
        await verify_workspace_access(
            request=request,
            workspace_id=seed_workspace,
            workspace_user=active_workspace_user,
            db=db_session,
        )


@pytest.mark.parametrize(
    "method, role",
    [
        ("GET", "read_only"),  # 1 vs 1 (Equal)
        ("PATCH", "edit_only"),  # 2 vs 2 (Equal)
        ("POST", "full_admin"),  # 2 vs 3 (Exceeds)
        ("OPTIONS", "read_only"),  # 1 vs 1 (Equal)
        ("HEAD", "full_admin"),  # 1 vs 3 (Exceeds)
    ],
)
async def test_verify_workspace_access_sufficient_permissions(
    method,
    role,
    db_session,
    seed_workspace,
    active_workspace_user,
    active_subscription,  # noqa
):
    """
    Verifies boundary conditions where the user's role weight exactly matches
    or exceeds the HTTP method's required weight.
    """
    request = MagicMock()
    request.method = method

    # Modify role dynamically
    active_workspace_user.role = role

    # Should execute successfully without raising any exceptions
    await verify_workspace_access(
        request=request,
        workspace_id=seed_workspace,
        workspace_user=active_workspace_user,
        db=db_session,
    )
