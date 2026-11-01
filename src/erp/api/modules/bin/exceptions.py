from erp.core.exceptions import BaseAppError


class BinNotFoundError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            detail="Bin not found.",
        )


class BinHasInventoryItemsError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=400,
            detail="Cannot delete bin that contains active inventory items.",
        )
