from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from erp.api.auth.dependencies import get_current_workspace_user
from erp.api.auth.exceptions import InsufficientPermissionsError
from erp.api.pricing.exceptions import ActiveSubscriptionNotFoundError
from erp.api.pricing.models import PricingSubscription
from erp.api.workspace_user.models import WorkspaceUser
from erp.database.base import get_db

ROLE_WEIGHTS = {"full_admin": 3, "edit_only": 2, "read_only": 1}

# Map HTTP methods to the minimum required role weight
METHOD_WEIGHTS = {
    "GET": 1,  # read_only, edit_only, full_admin
    "OPTIONS": 1,
    "HEAD": 1,
    "POST": 2,  # edit_only, full_admin
    "PUT": 2,
    "PATCH": 2,
    "DELETE": 3,  # full_admin only
}


async def verify_workspace_access(
    request: Request,
    workspace_id: UUID,
    # CHECK 1: This sub-dependency guarantees an active, authenticated workspace user
    workspace_user: Annotated[WorkspaceUser, Depends(get_current_workspace_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WorkspaceUser:
    """
    Master dependency for workspace routes.
    Validates active session, workspace membership, and HTTP method permissions.
    """

    # CHECK 2: Verify Pricing Subscription existence
    subscription_query = select(PricingSubscription.plan_id).where(
        PricingSubscription.workspace_id == workspace_id, PricingSubscription.is_active.is_(True)
    )

    result = await db.execute(subscription_query)
    subscription = result.scalar_one_or_none()

    if not subscription:
        raise ActiveSubscriptionNotFoundError()

    # CHECK 3: Verify their role weight against the HTTP method
    required_weight = METHOD_WEIGHTS.get(request.method.upper(), 3)
    user_weight = ROLE_WEIGHTS.get(workspace_user.role.lower(), 0)

    if user_weight < required_weight:
        raise InsufficientPermissionsError()

    request.state.workspace_user = workspace_user
    request.state.subscription_id = subscription

    return workspace_user
