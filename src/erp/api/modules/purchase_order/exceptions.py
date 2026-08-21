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
