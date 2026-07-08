from fastapi import status

from src.erp.core.exceptions import BaseAppError


class WorkspaceUserNotFoundError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace member not found or access record lookup failed.",
        )


class WorkspaceUserAlreadyInWorkspaceError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workspace user is already an active member of this workspace.",
        )


class SelfModificationBlockedError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Security Violation: You cannot alter your own system privileges.",
        )


class SelfEvictionBlockedError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Security Violation: Self-eviction blocked. Contact another administrator to leave.",
        )


class RankImmunityViolationError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: Target member maintains superior or equal administrative rank immunity.",
        )


class PrivilegeEscalationBlockedError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: You cannot escalate privileges beyond your own authorisation ceiling.",
        )
