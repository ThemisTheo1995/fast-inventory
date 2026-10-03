import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Enum, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from erp.api.base.models import BaseModel
from erp.api.search.enums import EntityTypeEnum


class GlobalSearchIndex(BaseModel):
    __tablename__ = "global_search_index"
    __table_args__ = (UniqueConstraint("workspace_id", "entity_type", "entity_id", name="uix_workspace_entity"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(index=True)

    entity_type: Mapped[EntityTypeEnum] = mapped_column(
        Enum(
            EntityTypeEnum,
            native_enum=False,
            length=50,
        ),
        default=None,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(index=True)

    url: Mapped[str] = mapped_column(String(1000))

    title: Mapped[str] = mapped_column(String(255))
    snippet: Mapped[str | None] = mapped_column(String(500), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768), nullable=True)
