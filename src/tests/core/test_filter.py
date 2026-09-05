import enum
from typing import ClassVar
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import Column, Integer, String, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import declarative_base

from src.erp.core.filter import BaseFilter, FilterOption, FilterSpec

# ==============================================================================
# 1. SETUP & MOCKS
# ==============================================================================

Base = declarative_base()


class MockModel(Base):
    """A dummy SQLAlchemy model to test filter applications."""

    __tablename__ = "mock_table"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    status = Column(String)
    age = Column(Integer)
    price = Column(Integer)


class MockStatusEnum(enum.Enum):
    """A mock enum to test enum parsing for UI filters."""

    ACTIVE = "active"
    INACTIVE = "inactive"

    # Simulating a custom label property if it exists
    @property
    def label(self):
        return f"Status: {self.name.title()}"


# Mock async/sync callables for UI filters
async def async_mock_options(_db, _workspace_id):
    return [FilterOption(label="Async Option", value="async_val")]


def sync_mock_options(_db, _workspace_id):
    return [FilterOption(label="Sync Option", value="sync_val")]


async def async_mock_range(_db, _workspace_id):
    return (10.0, 100.0)


def sync_mock_range(_db, _workspace_id):
    return (0.0, 50.0)


class TestFilter(BaseFilter):
    """A mock filter implementing all operator types and UI configurations."""

    name_eq: str | None = None
    name_ilike: str | None = None
    status_in: list[str] | None = None
    age_gte: int | None = None
    age_lte: int | None = None
    price_between_str: str | None = None
    price_between_tuple: tuple[int, int] | None = None

    # Used for testing edge cases
    unmapped_field: str | None = None

    __filter_config__: ClassVar[dict[str, FilterSpec]] = {
        "name_eq": FilterSpec(column_name="name", operator="eq"),
        "name_ilike": FilterSpec(column_name="name", operator="ilike"),
        "status_in": FilterSpec(column_name="status", operator="in", enum_type=MockStatusEnum),
        "age_gte": FilterSpec(column_name="age", operator="gte"),
        "age_lte": FilterSpec(column_name="age", operator="lte"),
        "price_between_str": FilterSpec(
            column_name="price", operator="between", type="range", range_fn=async_mock_range
        ),
        "price_between_tuple": FilterSpec(
            column_name="price", operator="between", type="range", range_fn=sync_mock_range
        ),
        "sync_options": FilterSpec(column_name="name", operator="eq", options_fn=sync_mock_options),
        "async_options": FilterSpec(column_name="name", operator="eq", options_fn=async_mock_options),
    }


# ==============================================================================
# 2. QUERY APPLICATION TESTS (`apply` method)
# ==============================================================================


def test_apply_ignores_empty_and_unmapped_values():
    """Ensures None, empty strings, and missing configs do not modify the query."""
    base_query = select(MockModel)

    # empty string, None, and unmapped fields
    filt = TestFilter(name_eq="", age_gte=None, unmapped_field="test")
    filtered_query = filt.apply(base_query, MockModel)

    compiled = str(filtered_query.compile(compile_kwargs={"literal_binds": True}))

    # The query should not have a WHERE clause
    assert "WHERE" not in compiled


def test_apply_standard_operators():
    """Tests eq, ilike, in, gte, lte operators."""
    base_query = select(MockModel)

    filt = TestFilter(
        name_eq="John",
        name_ilike="Doe",
        status_in=["active", "pending"],
        age_gte=18,
        age_lte=65,
    )

    filtered_query = filt.apply(base_query, MockModel)

    compiled = str(filtered_query.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))

    assert "mock_table.name = 'John'" in compiled
    assert "mock_table.name ILIKE '%%Doe%%'" in compiled
    assert "mock_table.status IN ('active', 'pending')" in compiled
    assert "mock_table.age >= 18" in compiled
    assert "mock_table.age <= 65" in compiled


def test_apply_between_operator_string():
    """Tests the 'between' operator when provided as a comma-separated string."""
    base_query = select(MockModel)

    filt = TestFilter(price_between_str="100,500")
    filtered_query = filt.apply(base_query, MockModel)
    compiled = str(filtered_query.compile(compile_kwargs={"literal_binds": True}))

    assert "mock_table.price BETWEEN 100.0 AND 500.0" in compiled


def test_apply_between_operator_tuple():
    """Tests the 'between' operator when provided as a tuple/list."""
    base_query = select(MockModel)

    filt = TestFilter(price_between_tuple=(50, 200))
    filtered_query = filt.apply(base_query, MockModel)
    compiled = str(filtered_query.compile(compile_kwargs={"literal_binds": True}))

    assert "mock_table.price BETWEEN 50 AND 200" in compiled


# ==============================================================================
# 3. UI FILTER BUILDER TESTS (`build_ui_filters` method)
# ==============================================================================


@pytest.mark.asyncio
async def test_build_ui_filters_enum_parsing():
    """Ensures enums are correctly mapped to UI options with their labels."""
    mock_db = AsyncMock()
    workspace_id = uuid4()

    filt = TestFilter()
    ui_filters = await filt.build_ui_filters(mock_db, workspace_id)

    status_ui_filter = next(f for f in ui_filters if f.key == "status_in")

    assert status_ui_filter.type == "select"
    assert len(status_ui_filter.options) == 2

    # Check that it used the custom @property 'label' from the Enum
    assert status_ui_filter.options[0].label == "Status: Active"
    assert status_ui_filter.options[0].value == "active"


@pytest.mark.asyncio
async def test_build_ui_filters_options_functions():
    """Ensures both sync and async functions can provide options."""
    mock_db = AsyncMock()
    workspace_id = uuid4()

    filt = TestFilter()
    ui_filters = await filt.build_ui_filters(mock_db, workspace_id)

    sync_options_filter = next(f for f in ui_filters if f.key == "sync_options")
    assert sync_options_filter.options[0].label == "Sync Option"

    async_options_filter = next(f for f in ui_filters if f.key == "async_options")
    assert async_options_filter.options[0].label == "Async Option"


@pytest.mark.asyncio
async def test_build_ui_filters_range_functions():
    """Ensures both sync and async functions can provide min/max ranges."""
    mock_db = AsyncMock()
    workspace_id = uuid4()

    filt = TestFilter()
    ui_filters = await filt.build_ui_filters(mock_db, workspace_id)

    async_range_filter = next(f for f in ui_filters if f.key == "price_between_str")
    assert async_range_filter.type == "range"
    assert async_range_filter.min == 10.0
    assert async_range_filter.max == 100.0

    sync_range_filter = next(f for f in ui_filters if f.key == "price_between_tuple")
    assert sync_range_filter.type == "range"
    assert sync_range_filter.min == 0.0
    assert sync_range_filter.max == 50.0


def test_apply_skips_nonexistent_model_column():
    """Ensures filter specs referencing columns missing from the target model are safely skipped."""

    class MissingColumnFilter(BaseFilter):
        invalid_field: str | None = None

        __filter_config__: ClassVar[dict[str, FilterSpec]] = {
            "invalid_field": FilterSpec(column_name="does_not_exist", operator="eq"),
        }

    base_query = select(MockModel)
    filt = MissingColumnFilter(invalid_field="test_value")
    filtered_query = filt.apply(base_query, MockModel)

    compiled = str(filtered_query.compile(compile_kwargs={"literal_binds": True}))
    assert "WHERE" not in compiled
