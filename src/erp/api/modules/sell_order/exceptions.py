from src.erp.core.exceptions import BaseAppError


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
