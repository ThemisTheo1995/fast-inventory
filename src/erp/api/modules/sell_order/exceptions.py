from erp.core.exceptions import BaseAppError


class SellOrderNotFoundError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            detail="Sell order not found.",
        )


class SellOrderExistsError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            detail="Sell order with received SO number already exists.",
        )


class SellOrderLineNotFoundError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            detail="Sell order line not found.",
        )


class SellOrderStatusTerminalError(BaseAppError):
    def __init__(self, old_status: str) -> None:
        super().__init__(
            status_code=409,
            detail=f"Cannot change status from terminal state: {old_status}",
        )


class SellOrderStatusTransitionError(BaseAppError):
    def __init__(
        self,
        old_status: str,
        new_status: str,
    ) -> None:
        super().__init__(
            status_code=409,
            detail=(f"Invalid status transition: {old_status} -> {new_status}"),
        )


class SellOrderNotEditableError(BaseAppError):
    def __init__(self, status: str) -> None:
        super().__init__(
            status_code=409,
            detail=f"Cannot modify lines on a {status} sell order.",
        )


class SellOrderCannotDeleteError(BaseAppError):
    def __init__(self, status: str) -> None:
        super().__init__(
            status_code=409,
            detail=f"Cannot delete a sell order in {status} status. Cancel it first.",
        )


class SellOrderLineItemChangeError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            detail="Remove the line and add a new one.",
        )
