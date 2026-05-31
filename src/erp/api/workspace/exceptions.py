from fastapi import HTTPException, status


class WorkspaceNotFound(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this workspace or it does not exist.",
            headers={"WWW-Authenticate": "Bearer"},
        )


class WorkspaceMemberNotFound(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace member not found or access record lookup failed.",
        )


class UserAlreadyActiveMember(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already an active member of this workspace.",
        )


class SelfModificationBlocked(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Security Violation: You cannot alter your own system privileges.",
        )


class SelfEvictionBlocked(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Security Violation: Self-eviction blocked. Contact another administrator to leave.",
        )


class RankImmunityViolation(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: Target member maintains superior or equal administrative rank immunity.",
        )


class PrivilegeEscalationBlocked(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: You cannot escalate privileges beyond your own authorization ceiling.",
        )
