from fastapi import status

from erp.core.exceptions import BaseAppError


class ActiveSubscriptionNotFoundError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active pricing plan found.",
        )
