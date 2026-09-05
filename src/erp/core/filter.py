import inspect
from collections.abc import Callable
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

OperatorType = Literal["eq", "ilike", "in", "gte", "lte", "between"]


class FilterOption(BaseModel):
    label: str
    value: Any = ""


class TableFilter(BaseModel):
    key: str
    label: str | None = None
    placeholder: str | None = None
    type: Literal["select", "range"] = "select"
    options: list[FilterOption] = Field(default_factory=list)
    min: float | None = None
    max: float | None = None
    step: float | None = None
    prefix: str | None = None


class FilterSpec:
    def __init__(
        self,
        column_name: str,
        operator: OperatorType = "eq",
        label: str | None = None,
        placeholder: str | None = None,
        type: Literal["select", "range"] = "select",
        enum_type: type[Enum] | None = None,
        options_fn: Callable[[AsyncSession, UUID], list[FilterOption]] | None = None,
        # Range-specific configurations
        min_val: float | None = None,
        max_val: float | None = None,
        range_fn: Callable[[AsyncSession, UUID], tuple[float, float]] | None = None,
        step: float | None = None,
        prefix: str | None = None,
    ) -> None:
        self.column_name = column_name
        self.operator = operator
        self.label = label or column_name.replace("_", " ").title()
        self.placeholder = placeholder or self.label
        self.type = type
        self.enum_type = enum_type
        self.options_fn = options_fn
        self.min_val = min_val
        self.max_val = max_val
        self.range_fn = range_fn
        self.step = step
        self.prefix = prefix


class BaseFilter(BaseModel):
    __filter_config__: dict[str, FilterSpec] = {}

    def apply(self, query: Select, model: type) -> Select:
        dump = self.model_dump(exclude_unset=True)

        for field_name, value in dump.items():
            if value is None or value == "":
                continue

            spec = self.__filter_config__.get(field_name)
            if not spec:
                continue

            column = getattr(model, spec.column_name, None)
            if column is None:
                continue

            if spec.operator == "eq":
                query = query.where(column == value)
            elif spec.operator == "ilike":
                query = query.where(column.ilike(f"%{value}%"))
            elif spec.operator == "in" and isinstance(value, (list, tuple, set)):
                query = query.where(column.in_(value))
            elif spec.operator == "gte":
                query = query.where(column >= value)
            elif spec.operator == "lte":
                query = query.where(column <= value)
            elif spec.operator == "between":
                if isinstance(value, str) and "," in value:
                    min_v, max_v = value.split(",", 1)
                    query = query.where(column.between(float(min_v), float(max_v)))
                elif isinstance(value, (list, tuple)) and len(value) == 2:
                    query = query.where(column.between(value[0], value[1]))

        return query

    async def build_ui_filters(self, db: AsyncSession, workspace_id: UUID) -> list[TableFilter]:
        table_filters: list[TableFilter] = []

        for field_name, spec in self.__filter_config__.items():
            options: list[FilterOption] = []
            min_val = spec.min_val
            max_val = spec.max_val

            if spec.enum_type:
                for item in spec.enum_type:
                    label = getattr(item, "label", item.name.replace("_", " ").title())
                    options.append(FilterOption(label=label, value=item.value))
            elif spec.options_fn:
                if inspect.iscoroutinefunction(spec.options_fn):
                    options = await spec.options_fn(db, workspace_id)
                else:
                    options = spec.options_fn(db, workspace_id)

            if spec.type == "range" and spec.range_fn:
                if inspect.iscoroutinefunction(spec.range_fn):
                    min_val, max_val = await spec.range_fn(db, workspace_id)
                else:
                    min_val, max_val = spec.range_fn(db, workspace_id)

            table_filters.append(
                TableFilter(
                    key=field_name,
                    label=spec.label,
                    placeholder=spec.placeholder,
                    type=spec.type,
                    options=options,
                    min=min_val,
                    max=max_val,
                    step=spec.step,
                    prefix=spec.prefix,
                )
            )

        return table_filters
