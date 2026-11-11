from erp.core.exceptions import BaseAppError


class InsufficientInventoryError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=400,
            detail="Not enough physical stock. This movement would make the stock quantity go below zero.",
        )


class InventoryNotEmptyError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=400,
            detail="Inventory is not empty.",
        )


class InventoryNotFoundError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            detail="Inventory not found.",
        )


class TransferStockQuantityNegativeError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=400,
            detail="Transfer quantity must be greater than zero.",
        )


class TransferStockSameBinError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=400,
            detail="Source and destination bins cannot be the same.",
        )


class PickPackInvalidQuantityError(BaseAppError):
    def __init__(self, detail: str = "Quantity must be greater than zero.") -> None:
        super().__init__(
            status_code=400,
            detail=detail,
        )
