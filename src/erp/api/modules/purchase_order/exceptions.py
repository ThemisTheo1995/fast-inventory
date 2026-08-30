from src.erp.core.exceptions import BaseAppError


class PurchaseOrderNotFoundError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            detail="Purchase order not found.",
        )


class PurchaseOrderExistsError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            detail="Purchase order with received PO number already exists.",
        )


class PurchaseOrderLineNotFoundError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            detail="Purchase order line not found.",
        )


class PurchaseOrderCannotDeleteError(ValueError):
    def __init__(self, status_label: str) -> None:
        super().__init__(f"Cannot delete purchase order in status: {status_label}. Cancel the order first.")


class PurchaseOrderLineItemChangeError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            detail="Remove the line and add a new one.",
        )


class PurchaseOrderNotEditableError(BaseAppError):
    def __init__(self, status: str) -> None:
        super().__init__(
            status_code=409,
            detail=f"Cannot modify lines on a {status} purchase order.",
        )


class PurchaseOrderStatusTransitionError(BaseAppError):
    def __init__(
        self,
        old_status: str,
        new_status: str,
    ) -> None:
        super().__init__(
            status_code=409,
            detail=(f"Invalid status transition: {old_status} -> {new_status}"),
        )
