import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Uuid, func, inspect
from sqlalchemy.orm import Load, Mapped, mapped_column, selectinload

from erp.api.base.exceptions import InvalidExpandError
from erp.core.utils import utc_now
from erp.database.base import Base


class BaseModel(Base):
    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)

    # Combined Python default + Database server_default
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now(), nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, server_default=func.now(), nullable=False
    )

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def soft_delete(self) -> None:
        self.is_deleted = True
        self.deleted_at = utc_now()


def build_expand_tree(
    expand_fields: list[str],
    max_depth: int = 3,
) -> dict[str, Any]:
    """
    Convert dot-notation expansion paths into a nested tree.

    Example:

        [
            "item",
            "item.stock_movements",
            "item.workspace",
        ]

    becomes:

        {
            "item": {
                "stock_movements": {},
                "workspace": {},
            }
        }
    """

    tree: dict[str, Any] = {}

    for field_path in expand_fields:
        if not field_path:
            continue

        parts = field_path.split(".")

        if len(parts) > max_depth:
            msg = f"Expand path '{field_path}' exceeds the maximum depth of {max_depth}."
            raise InvalidExpandError(msg)

        current = tree

        for part in parts:
            if not part:
                msg = f"Invalid expand path '{field_path}'."
                raise InvalidExpandError(msg)

            current = current.setdefault(part, {})

    return tree


def build_loader_options(
    model: type,
    expand_fields: list[str] | None,
    max_depth: int = 3,
) -> list[Load]:
    """
    Convert expand paths into SQLAlchemy selectinload options.

    Example:

        build_loader_options(
            Inventory,
            [
                "item",
                "item.stock_movements",
            ],
        )

    produces the equivalent of:

        selectinload(Inventory.item).selectinload(
            Item.stock_movements
        )
    """

    if not expand_fields:
        return []

    tree = build_expand_tree(
        expand_fields,
        max_depth=max_depth,
    )

    return _build_loader_options(
        model=model,
        tree=tree,
    )


def _build_loader_options(
    model: type,
    tree: dict[str, Any],
) -> list[Load]:
    """Recursively build SQLAlchemy loader options."""

    mapper = inspect(model)
    options: list[Load] = []

    for relationship_name, children in tree.items():
        relationship = mapper.relationships.get(relationship_name)

        msg = f"'{relationship_name}' is not a relationship on {model.__name__}."

        if relationship is None:
            raise InvalidExpandError(msg)

        attribute = getattr(model, relationship_name)

        loader = selectinload(attribute)

        if children:
            related_model = relationship.mapper.class_

            child_options = _build_loader_options(
                model=related_model,
                tree=children,
            )

            loader = loader.options(*child_options)

        options.append(loader)

    return options
