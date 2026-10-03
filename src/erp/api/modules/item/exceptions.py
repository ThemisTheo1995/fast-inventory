from erp.core.exceptions import BaseAppError


class ItemNotFoundError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            detail="Item not found.",
        )


class ItemExistsError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            detail="Item with received SKU already exists.",
        )
