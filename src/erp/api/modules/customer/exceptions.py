from src.erp.core.exceptions import BaseAppError


class CustomerNotFoundError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            detail="Customer not found.",
        )


class CustomerEmailExistsError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            detail="A customer with this email already exists in this workspace.",
        )


class CustomerNameMustNotContainNumbersError(BaseAppError):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            detail="Customer name must not contain numbers.",
        )
