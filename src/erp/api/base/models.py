import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from src.erp.core.utils import utc_now
from src.erp.database.base import Base


class BaseModel(Base):
    """
    Base model that includes common fields for all models.
    This is an abstract class and should not be instantiated directly.
    """

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def soft_delete(self) -> None:
        """Soft deletes the record by setting is_deleted to True and updating the deleted_at timestamp."""
        self.is_deleted = True
        self.deleted_at = utc_now()
