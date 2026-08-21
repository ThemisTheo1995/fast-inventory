import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.erp.api.modules.sell_order.schemas import (
    SellOrderCreate,
    SellOrderLineCreate,
    SellOrderLineResponse,
    SellOrderLineUpdate,
    SellOrderPaginatedResponse,
    SellOrderResponse,
    SellOrderUpdate,
)

# =======================================================
# MOCK ORM MODELS FOR DATABASE MAPPING TESTS
# =======================================================


class MockItemORM:
    """Mock ORM model matching ItemResponse constraints."""

    def __init__(
        self,
        item_id: uuid.UUID | None = None,
        workspace_id: uuid.UUID | None = None,
        title: str = "Widget Pro",
        sku: str = "WDG-PRO-001",
        base_price: int | None = 1500,
    ):
        self.id = item_id or uuid.uuid4()
        self.workspace_id = workspace_id or uuid.uuid4()
        self.title = title
        self.sku = sku
        self.base_price = base_price
        self.created_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)


class MockCustomerORM:
    """Mock ORM model matching CustomerResponse constraints."""

    def __init__(
        self,
        cust_id: uuid.UUID | None = None,
        workspace_id: uuid.UUID | None = None,
        first_name: str = "john",
        last_name: str = "doe",
        email: str = "john.doe@example.com",
    ):
        self.id = cust_id or uuid.uuid4()
        self.workspace_id = workspace_id or uuid.uuid4()
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.created_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)


class MockLineORM:
    """Mock ORM model matching SellOrderLineResponse constraints."""

    def __init__(
        self,
        line_id: uuid.UUID | None = None,
        so_id: uuid.UUID | None = None,
        item_id: uuid.UUID | None = None,
        quantity: int = 5,
        unit_cost: int = 200,
        item: MockItemORM | None = None,
    ):
        self.id = line_id or uuid.uuid4()
        self.sell_order_id = so_id or uuid.uuid4()
        self.item_id = item_id
        self.quantity = quantity
        self.unit_cost = unit_cost
        self.item = item


class MockSellOrderORM:
    """Mock ORM model matching SellOrderResponse constraints."""

    def __init__(
        self,
        so_id: uuid.UUID | None = None,
        workspace_id: uuid.UUID | None = None,
        so_number: str = "SO-2026-001",
        customer_id: uuid.UUID | None = None,
        status: str = "DRAFT",
        total_amount: int = 1000,
        lines: list[MockLineORM] | None = None,
        customer: MockCustomerORM | None = None,
    ):
        self.id = so_id or uuid.uuid4()
        self.workspace_id = workspace_id or uuid.uuid4()
        self.so_number = so_number
        self.customer_id = customer_id
        self.status = status
        self.total_amount = total_amount
        self.created_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)
        self.sell_order_lines = lines if lines is not None else []
        self.customer = customer


# =======================================================
# 1. SELL ORDER LINE SCHEMAS (Create, Update, Response)
# =======================================================


@pytest.mark.parametrize("schema_cls", [SellOrderLineCreate, SellOrderLineUpdate])
def test_sell_order_line_valid_instantiation(schema_cls):
    """Verifies happy path for line payloads with and without item_id."""
    item_id = uuid.uuid4()

    # With item_id
    line1 = schema_cls(item_id=item_id, quantity=10, unit_cost=150)
    assert line1.item_id == item_id
    assert line1.quantity == 10
    assert line1.unit_cost == 150

    # Without item_id (None)
    line2 = schema_cls(item_id=None, quantity=1, unit_cost=0)
    assert line2.item_id is None
    assert line2.quantity == 1
    assert line2.unit_cost == 0


@pytest.mark.parametrize("schema_cls", [SellOrderLineCreate, SellOrderLineUpdate])
@pytest.mark.parametrize(
    "quantity,is_valid",
    [
        (1, True),
        (100, True),
        (999999, True),
        (0, False),  # Boundary: ge=1 constraint violated
        (-1, False),  # Negative quantity rejected
        (-50, False),
    ],
)
def test_sell_order_line_quantity_boundary_constraints(schema_cls, quantity, is_valid):
    """Verifies that quantity strictly enforces ge=1 boundary."""
    payload = {"quantity": quantity, "unit_cost": 100}

    if is_valid:
        schema = schema_cls(**payload)
        assert schema.quantity == quantity
    else:
        with pytest.raises(ValidationError) as exc_info:
            schema_cls(**payload)
        assert "Input should be greater than or equal to 1" in str(exc_info.value)


@pytest.mark.parametrize("schema_cls", [SellOrderLineCreate, SellOrderLineUpdate])
@pytest.mark.parametrize(
    "unit_cost,is_valid",
    [
        (0, True),  # Boundary: ge=0 allows zero price items
        (1, True),
        (5000, True),
        (-1, False),  # Boundary: negative price rejected
        (-100, False),
    ],
)
def test_sell_order_line_unit_cost_boundary_constraints(schema_cls, unit_cost, is_valid):
    """Verifies that unit_cost strictly enforces ge=0 boundary."""
    payload = {"quantity": 1, "unit_cost": unit_cost}

    if is_valid:
        schema = schema_cls(**payload)
        assert schema.unit_cost == unit_cost
    else:
        with pytest.raises(ValidationError) as exc_info:
            schema_cls(**payload)
        assert "Input should be greater than or equal to 0" in str(exc_info.value)


@pytest.mark.parametrize("schema_cls", [SellOrderLineCreate, SellOrderLineUpdate])
def test_sell_order_line_missing_required_fields(schema_cls):
    """Verifies that quantity and unit_cost are strictly required."""
    with pytest.raises(ValidationError) as exc_info:
        schema_cls(quantity=5)
    assert "unit_cost" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        schema_cls(unit_cost=100)
    assert "quantity" in str(exc_info.value)


@pytest.mark.parametrize("schema_cls", [SellOrderLineCreate, SellOrderLineUpdate])
def test_sell_order_line_invalid_item_id_type(schema_cls):
    """Verifies that non-UUID strings trigger validation error on item_id."""
    payload = {"item_id": "invalid-uuid-string", "quantity": 1, "unit_cost": 10}
    with pytest.raises(ValidationError) as exc_info:
        schema_cls(**payload)
    assert "Input should be a valid UUID" in str(exc_info.value)


def test_sell_order_line_response_dictionary_deserialization():
    """Verifies SellOrderLineResponse maps correctly when given nested ItemResponse dictionary."""
    line_id = uuid.uuid4()
    so_id = uuid.uuid4()
    item_id = uuid.uuid4()
    now = datetime.now(UTC)

    # 1. Line without nested item object
    payload_no_item = {
        "id": line_id,
        "sell_order_id": so_id,
        "item_id": None,
        "quantity": 2,
        "unit_cost": 50,
        "item": None,
    }
    schema_no_item = SellOrderLineResponse(**payload_no_item)
    assert schema_no_item.id == line_id
    assert schema_no_item.item is None

    # 2. Line with populated nested item object (matching ItemResponse schema)
    item_dict = {
        "id": item_id,
        "workspace_id": uuid.uuid4(),
        "title": "Industrial Bolt",
        "sku": "BLT-009",
        "base_price": 50,
        "created_at": now,
        "updated_at": now,
    }
    payload_with_item = {
        **payload_no_item,
        "item_id": item_id,
        "item": item_dict,
    }
    schema_with_item = SellOrderLineResponse(**payload_with_item)
    assert schema_with_item.item is not None
    assert schema_with_item.item.id == item_id
    assert schema_with_item.item.title == "Industrial Bolt"
    assert schema_with_item.item.sku == "BLT-009"
    assert schema_with_item.item.base_price == 50


def test_sell_order_line_response_item_base_price_can_be_none():
    """Verifies ItemResponse inside SellOrderLineResponse accepts base_price=None."""
    now = datetime.now(UTC)
    item_dict = {
        "id": uuid.uuid4(),
        "workspace_id": uuid.uuid4(),
        "title": "Custom Service",
        "sku": "SRV-001",
        "base_price": None,  # Optional int
        "created_at": now,
        "updated_at": now,
    }
    payload = {
        "id": uuid.uuid4(),
        "sell_order_id": uuid.uuid4(),
        "item_id": item_dict["id"],
        "quantity": 1,
        "unit_cost": 1000,
        "item": item_dict,
    }
    schema = SellOrderLineResponse(**payload)
    assert schema.item is not None
    assert schema.item.base_price is None


def test_sell_order_line_response_from_orm():
    """Verifies SellOrderLineResponse maps correctly from database ORM objects using model_validate."""
    item_orm = MockItemORM(title="Gearbox", sku="GBX-100", base_price=2500)
    line_orm = MockLineORM(quantity=3, unit_cost=2400, item=item_orm, item_id=item_orm.id)

    schema = SellOrderLineResponse.model_validate(line_orm)

    assert schema.id == line_orm.id
    assert schema.sell_order_id == line_orm.sell_order_id
    assert schema.quantity == 3
    assert schema.unit_cost == 2400
    assert schema.item is not None
    assert schema.item.id == item_orm.id
    assert schema.item.title == "Gearbox"
    assert schema.item.sku == "GBX-100"


# =======================================================
# 2. SELL ORDER CREATE SCHEMAS
# =======================================================


def test_sell_order_create_success():
    """Verifies successful instantiation of SellOrderCreate with nested line payloads."""
    line1 = {"quantity": 2, "unit_cost": 500}
    line2 = {"item_id": uuid.uuid4(), "quantity": 1, "unit_cost": 100}

    payload = {
        "so_number": "SO-2026-001",
        "customer_id": uuid.uuid4(),
        "status": "DRAFT",
        "sell_order_lines": [line1, line2],
    }

    schema = SellOrderCreate(**payload)
    assert schema.so_number == "SO-2026-001"
    assert schema.status == "DRAFT"
    assert len(schema.sell_order_lines) == 2
    assert isinstance(schema.sell_order_lines[0], SellOrderLineCreate)
    assert schema.sell_order_lines[0].quantity == 2


def test_sell_order_create_default_status():
    """Verifies that status defaults to 'DRAFT' when omitted."""
    payload = {"so_number": "SO-001", "sell_order_lines": []}
    schema = SellOrderCreate(**payload)
    assert schema.status == "DRAFT"


@pytest.mark.parametrize(
    "so_number,is_valid",
    [
        ("A", True),
        ("SO-100", True),
        ("X" * 100, True),  # Boundary: Exactly 100 chars
        ("X" * 101, False),  # Boundary: 101 chars exceeds limit
    ],
)
def test_sell_order_create_so_number_length_boundary(so_number, is_valid):
    """Verifies so_number constraint of max_length=100."""
    payload = {"so_number": so_number, "sell_order_lines": []}

    if is_valid:
        schema = SellOrderCreate(**payload)
        assert schema.so_number == so_number
    else:
        with pytest.raises(ValidationError) as exc_info:
            SellOrderCreate(**payload)
        assert "String should have at most 100 characters" in str(exc_info.value)


@pytest.mark.parametrize(
    "status,is_valid",
    [
        ("DRAFT", True),
        ("CONFIRMED", True),
        ("INVALID_STATUS", False),
        ("S" * 51, False),
    ],
)
def test_sell_order_create_status_length_boundary(status, is_valid):
    """Verifies status only accepts valid SOStatusEnum values."""
    payload = {"so_number": "SO-001", "status": status, "sell_order_lines": []}

    if is_valid:
        schema = SellOrderCreate(**payload)
        assert schema.status == status
    else:
        with pytest.raises(ValidationError) as exc_info:
            SellOrderCreate(**payload)
        assert "Input should be 'DRAFT'" in str(exc_info.value)


def test_sell_order_create_missing_required_fields():
    """Verifies validation errors when so_number or sell_order_lines are omitted."""
    # Missing so_number
    with pytest.raises(ValidationError) as exc_info:
        SellOrderCreate(sell_order_lines=[])
    assert "so_number" in str(exc_info.value)

    # Missing sell_order_lines
    with pytest.raises(ValidationError) as exc_info:
        SellOrderCreate(so_number="SO-100")
    assert "sell_order_lines" in str(exc_info.value)


def test_sell_order_create_invalid_nested_line_triggers_error():
    """Verifies that invalid child data inside sell_order_lines invalidates the parent model."""
    invalid_line = {"quantity": -5, "unit_cost": 100}  # quantity < 1 invalid
    payload = {"so_number": "SO-999", "sell_order_lines": [invalid_line]}

    with pytest.raises(ValidationError) as exc_info:
        SellOrderCreate(**payload)
    assert "Input should be greater than or equal to 1" in str(exc_info.value)


# =======================================================
# 3. SELL ORDER UPDATE SCHEMAS
# =======================================================


def test_sell_order_update_allows_empty_instantiation():
    """Verifies SellOrderUpdate supports empty payloads for partial updates."""
    schema = SellOrderUpdate()
    assert schema.so_number is None
    assert schema.customer_id is None
    assert schema.status is None


def test_sell_order_update_partial_fields():
    """Verifies partial updates with individual or subsets of fields."""
    schema = SellOrderUpdate(status="CANCELLED")
    assert schema.status == "CANCELLED"
    assert schema.so_number is None
    assert schema.customer_id is None


def test_sell_order_update_explicit_none_dump():
    """Verifies explicit None values are properly preserved on model_dump."""
    schema = SellOrderUpdate(so_number=None, customer_id=None, status=None)
    dumped = schema.model_dump(exclude_unset=True)
    assert dumped == {"so_number": None, "customer_id": None, "status": None}


@pytest.mark.parametrize(
    "field,value,error_msg",
    [
        ("so_number", "X" * 101, "String should have at most 100 characters"),
        ("status", "INVALID_STATUS", "Input should be 'DRAFT'"),
        ("customer_id", "not-a-valid-uuid", "Input should be a valid UUID"),
    ],
)
def test_sell_order_update_field_constraint_violations(field, value, error_msg):
    """Verifies optional fields enforce constraints when bad values are passed."""
    payload = {field: value}
    with pytest.raises(ValidationError) as exc_info:
        SellOrderUpdate(**payload)
    assert error_msg in str(exc_info.value)


# =======================================================
# 4. SELL ORDER RESPONSE SCHEMAS (Mappings & ORM)
# =======================================================


def test_sell_order_response_full_dictionary():
    """Verifies full dictionary payload with nested lines and customer responses."""
    so_id = uuid.uuid4()
    ws_id = uuid.uuid4()
    cust_id = uuid.uuid4()
    now = datetime.now(UTC)

    customer_data = {
        "id": cust_id,
        "workspace_id": ws_id,
        "first_name": "alice",
        "last_name": "smith",
        "email": "alice@example.com",
        "created_at": now,
        "updated_at": now,
    }

    line_data = {
        "id": uuid.uuid4(),
        "sell_order_id": so_id,
        "item_id": None,
        "quantity": 10,
        "unit_cost": 100,
        "item": None,
    }

    payload = {
        "id": so_id,
        "workspace_id": ws_id,
        "so_number": "SO-FULL-01",
        "customer_id": cust_id,
        "status": "FULLFILLED",
        "total_amount": 1000,
        "created_at": now,
        "updated_at": now,
        "sell_order_lines": [line_data],
        "customer": customer_data,
    }

    schema = SellOrderResponse(**payload)
    assert schema.id == so_id
    assert schema.workspace_id == ws_id
    assert schema.so_number == "SO-FULL-01"
    assert schema.total_amount == 1000
    assert len(schema.sell_order_lines) == 1
    assert schema.customer is not None
    assert schema.customer.id == cust_id


def test_sell_order_response_optional_relationships_as_none():
    """Verifies SellOrderResponse works with empty lines and customer set to None."""
    now = datetime.now(UTC)
    payload = {
        "id": uuid.uuid4(),
        "workspace_id": uuid.uuid4(),
        "so_number": "SO-MINIMAL",
        "customer_id": None,
        "status": "DRAFT",
        "total_amount": 0,
        "created_at": now,
        "updated_at": now,
        "sell_order_lines": [],
        "customer": None,
    }

    schema = SellOrderResponse(**payload)
    assert schema.customer is None
    assert schema.sell_order_lines == []
    assert schema.total_amount == 0


def test_sell_order_response_missing_required_core_fields():
    """Verifies that failing to pass top-level metadata triggers validation errors."""
    payload = {
        "so_number": "SO-INCOMPLETE",
        "sell_order_lines": [],
        "customer": None,
    }

    with pytest.raises(ValidationError) as exc_info:
        SellOrderResponse(**payload)

    err = str(exc_info.value)
    assert "id" in err
    assert "workspace_id" in err
    assert "total_amount" in err
    assert "created_at" in err
    assert "updated_at" in err


def test_sell_order_response_full_orm_mapping():
    """Verifies model_validate on a deeply nested mock ORM tree (Order -> Customer, Lines -> Item)."""
    item_orm = MockItemORM(title="Precision Screw", sku="SCR-01", base_price=10)
    line_orm = MockLineORM(quantity=100, unit_cost=10, item=item_orm, item_id=item_orm.id)
    cust_orm = MockCustomerORM(first_name="bruce", last_name="wayne", email="bruce@wayne.com")

    so_orm = MockSellOrderORM(
        so_number="SO-ORM-TREE",
        total_amount=1000,
        status="CONFIRMED",
        lines=[line_orm],
        customer=cust_orm,
        customer_id=cust_orm.id,
    )

    schema = SellOrderResponse.model_validate(so_orm)

    # Validate parent order attributes
    assert schema.id == so_orm.id
    assert schema.so_number == "SO-ORM-TREE"
    assert schema.total_amount == 1000
    assert schema.status == "CONFIRMED"

    # Validate nested customer model
    assert schema.customer is not None
    assert schema.customer.id == cust_orm.id
    assert schema.customer.email == "bruce@wayne.com"

    # Validate nested line & item model
    assert len(schema.sell_order_lines) == 1
    line_schema = schema.sell_order_lines[0]
    assert line_schema.quantity == 100
    assert line_schema.unit_cost == 10
    assert line_schema.item is not None
    assert line_schema.item.title == "Precision Screw"
    assert line_schema.item.sku == "SCR-01"
    assert line_schema.item.base_price == 10


# =======================================================
# 5. PAGINATED RESPONSE SCHEMAS
# =======================================================


def test_sell_order_paginated_response_success():
    """Verifies pagination payload binds items list and total count properly."""
    now = datetime.now(UTC)
    so_id = uuid.uuid4()

    item_payload = {
        "id": so_id,
        "workspace_id": uuid.uuid4(),
        "so_number": "SO-PAGE-1",
        "customer_id": None,
        "status": "DRAFT",
        "total_amount": 500,
        "created_at": now,
        "updated_at": now,
        "sell_order_lines": [],
        "customer": None,
    }

    payload = {"items": [item_payload], "total": 1}

    schema = SellOrderPaginatedResponse(**payload)
    assert schema.total == 1
    assert len(schema.items) == 1
    assert isinstance(schema.items[0], SellOrderResponse)
    assert schema.items[0].id == so_id


def test_sell_order_paginated_response_empty_state():
    """Verifies edge case where total=0 and items=[] (zero search results)."""
    payload = {"items": [], "total": 0}
    schema = SellOrderPaginatedResponse(**payload)
    assert schema.total == 0
    assert schema.items == []


def test_sell_order_paginated_response_invalid_types():
    """Verifies validation error on type mismatch (non-integer total or bad item structure)."""
    # Bad total type
    with pytest.raises(ValidationError):
        SellOrderPaginatedResponse(items=[], total="invalid-number")

    # Bad item payload
    with pytest.raises(ValidationError):
        SellOrderPaginatedResponse(items=[{"invalid": "item"}], total=1)
