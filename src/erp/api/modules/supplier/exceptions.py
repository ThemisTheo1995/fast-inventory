from src.erp.core.exceptions import BaseAppError


class SupplierNotFoundError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            detail="Supplier not found.",
        )


class SupplierEmailExistsError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            detail="A supplier with this email already exists in this workspace.",
        )
