from typing import TypeVar

from sqlalchemy.orm import Load, Session

from src.erp.api.base.models import build_loader_options

ModelT = TypeVar("ModelT")


class BaseService[ModelT]:
    def __init__(
        self,
        db: Session,
        model: type[ModelT],
    ) -> None:
        self.db = db
        self.model = model

    def build_loader_options(
        self,
        expand: list[str] | None = None,
    ) -> list[Load]:
        return build_loader_options(
            self.model,
            expand,
        )
