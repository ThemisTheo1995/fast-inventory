from src.erp.core.exceptions import BaseAppError


class InsufficientInventoryError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=400,
            detail="Not enough stock. This movement would make the stock quantity go below zero.",
        )
