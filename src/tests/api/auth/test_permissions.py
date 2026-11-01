import pytest
from starlette.requests import Request

from erp.api.auth.exceptions import InsufficientPermissionsError
from erp.api.auth.permissions import verify_workspace_access
from erp.api.pricing.exceptions import ActiveSubscriptionNotFoundError


def make_request(
    method: str,
    endpoint_name: str = "test_endpoint",
) -> Request:
    async def endpoint():
        pass

    endpoint.__name__ = endpoint_name

    return Request(
        {
            "type": "http",
            "method": method,
            "path": "/test",
            "headers": [],
            "query_string": b"",
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
            "scheme": "http",
            "http_version": "1.1",
            "endpoint": endpoint,
        }
    )


# ==============================================================================
# SUBSCRIPTION TESTS
# ==============================================================================


async def test_verify_workspace_access_no_subscription(
    db_session,
    seed_workspace,
    active_workspace_user,
):
    """A workspace without an active subscription is rejected."""
    request = make_request("GET")

    with pytest.raises(ActiveSubscriptionNotFoundError):
        await verify_workspace_access(
            request=request,
            workspace_id=seed_workspace,
            workspace_user=active_workspace_user,
            db=db_session,
        )

    assert not hasattr(request.state, "workspace_user")
    assert not hasattr(request.state, "subscription_id")


async def test_verify_workspace_access_inactive_subscription_rejected(
    db_session,
    seed_workspace,
    active_workspace_user,
    active_subscription,
):
    """An inactive subscription does not grant workspace access."""
    active_subscription.is_active = False
    await db_session.commit()

    request = make_request("GET")

    with pytest.raises(ActiveSubscriptionNotFoundError):
        await verify_workspace_access(
            request=request,
            workspace_id=seed_workspace,
            workspace_user=active_workspace_user,
            db=db_session,
        )

    assert not hasattr(request.state, "workspace_user")
    assert not hasattr(request.state, "subscription_id")


async def test_verify_workspace_access_success_state_injection(
    db_session,
    seed_workspace,
    active_workspace_user,
    active_subscription,
):
    """A valid subscription and sufficient permissions inject request state."""
    request = make_request("DELETE")

    result = await verify_workspace_access(
        request=request,
        workspace_id=seed_workspace,
        workspace_user=active_workspace_user,
        db=db_session,
    )

    assert result == active_workspace_user
    assert request.state.workspace_user == active_workspace_user
    assert request.state.subscription_id == active_subscription.plan_id


# ==============================================================================
# INSUFFICIENT PERMISSIONS
# ==============================================================================


@pytest.mark.usefixtures("active_subscription")
@pytest.mark.parametrize(
    ("method", "role"),
    [
        ("POST", "read_only"),
        ("DELETE", "edit_only"),
        ("DELETE", "read_only"),
        ("PUT", "read_only"),
        ("UNKNOWN", "edit_only"),
        ("GET", "unknown"),
    ],
)
async def test_verify_workspace_access_insufficient_permissions(
    method, role, db_session, seed_workspace, active_workspace_user
):
    """Roles below the required method weight are rejected."""
    active_workspace_user.role = role

    request = make_request(method)

    with pytest.raises(InsufficientPermissionsError):
        await verify_workspace_access(
            request=request,
            workspace_id=seed_workspace,
            workspace_user=active_workspace_user,
            db=db_session,
        )

    assert not hasattr(request.state, "workspace_user")
    assert not hasattr(request.state, "subscription_id")


# ==============================================================================
# SUFFICIENT PERMISSIONS
# ==============================================================================


@pytest.mark.parametrize(
    ("method", "role"),
    [
        ("GET", "read_only"),
        ("OPTIONS", "read_only"),
        ("HEAD", "read_only"),
        ("PATCH", "edit_only"),
        ("POST", "edit_only"),
        ("PUT", "edit_only"),
        ("DELETE", "full_admin"),
        ("POST", "full_admin"),
        ("DELETE", "full_admin"),
    ],
)
async def test_verify_workspace_access_sufficient_permissions(
    method,
    role,
    db_session,
    seed_workspace,
    active_workspace_user,
    active_subscription,
):
    """Roles meeting or exceeding the required weight are accepted."""
    active_workspace_user.role = role

    request = make_request(method)

    result = await verify_workspace_access(
        request=request,
        workspace_id=seed_workspace,
        workspace_user=active_workspace_user,
        db=db_session,
    )

    assert result == active_workspace_user
    assert request.state.workspace_user == active_workspace_user
    assert request.state.subscription_id == active_subscription.plan_id


# ==============================================================================
# SPECIAL ELIGIBLE ROUTES
# ==============================================================================


@pytest.mark.parametrize(
    "endpoint_name",
    [
        "create_note",
        "update_note",
        "update_me",
    ],
)
async def test_verify_workspace_access_eligible_read_only_routes(
    endpoint_name,
    db_session,
    seed_workspace,
    active_workspace_user,
    active_subscription,
):
    """Eligible routes allow read-only users despite the HTTP method weight."""
    active_workspace_user.role = "read_only"

    request = make_request(
        method="POST",
        endpoint_name=endpoint_name,
    )

    result = await verify_workspace_access(
        request=request,
        workspace_id=seed_workspace,
        workspace_user=active_workspace_user,
        db=db_session,
    )

    assert result == active_workspace_user
    assert request.state.workspace_user == active_workspace_user
    assert request.state.subscription_id == active_subscription.plan_id


# ==============================================================================
# WORKSPACE ISOLATION
# ==============================================================================


async def test_verify_workspace_access_subscription_belongs_to_another_workspace(
    db_session,
    seed_workspace,
    alt_workspace,
    active_workspace_user,
    active_subscription,
):
    """A subscription for another workspace cannot authorize this workspace."""
    request = make_request("GET")

    # Move the subscription away from the workspace being checked.
    active_subscription.workspace_id = alt_workspace
    await db_session.commit()

    with pytest.raises(ActiveSubscriptionNotFoundError):
        await verify_workspace_access(
            request=request,
            workspace_id=seed_workspace,
            workspace_user=active_workspace_user,
            db=db_session,
        )

    assert not hasattr(request.state, "workspace_user")
    assert not hasattr(request.state, "subscription_id")
