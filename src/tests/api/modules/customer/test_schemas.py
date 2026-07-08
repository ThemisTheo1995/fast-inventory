import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.erp.api.modules.customer.exceptions import CustomerNameMustNotContainNumbersError
from src.erp.api.modules.customer.schemas import (
    CustomerCreate,
    CustomerPaginatedResponse,
    CustomerResponse,
    CustomerUpdate,
)

# --- 1. CUSTOM NAME VALIDATION & FORMATTING TESTS ---


@pytest.mark.parametrize(
    "raw_input,expected_output",
    [
        ("john doe", "John Doe"),
        ("  ALICE  ", "Alice"),
        ("jean-luc", "Jean-Luc"),
        ("O'CONNOR", "O'connor"),
        ("mary-jane smith", "Mary-Jane Smith"),
    ],
)
def test_name_formatting_and_capitalization(raw_input, expected_output):
    """Verifies that names are correctly trimmed, downcased, and title-cased via regex."""
    payload = {"first_name": raw_input, "last_name": "Smith", "email": "test@example.com"}
    schema = CustomerCreate(**payload)
    assert schema.first_name == expected_output


def test_name_containing_numbers_raises_domain_error():
    """Verifies that names containing digits instantly trigger your custom domain exception."""
    payload = {"first_name": "John3", "last_name": "Doe", "email": "john.doe@example.com"}
    with pytest.raises(CustomerNameMustNotContainNumbersError):
        CustomerCreate(**payload)


def test_last_name_handles_none_safely():
    """Verifies that last_name can be cleanly omitted or passed as None."""
    payload = {"first_name": "Jane", "last_name": None, "email": "jane@example.com"}
    schema = CustomerCreate(**payload)
    assert schema.last_name is None


# --- 2. FIELD BOUNDARY & CONSTRAINT TESTS ---


def test_first_name_too_short():
    """Verifies first_name requires at least 2 characters."""
    with pytest.raises(ValidationError) as exc_info:
        CustomerCreate(first_name="J", last_name="Doe", email="j@test.com")
    assert "String should have at least 2 characters" in str(exc_info.value)


@pytest.mark.parametrize(
    "field,value,error_msg",
    [
        ("first_name", "X" * 51, "String should have at most 50 characters"),
        ("last_name", "Y" * 51, "String should have at most 50 characters"),
    ],
)
def test_name_length_max_boundaries(field, value, error_msg):
    """Verifies character limits capped at 50 elements trigger structural validation errors."""
    base_payload = {"first_name": "John", "last_name": "Doe", "email": "test@test.com"}
    base_payload[field] = value

    with pytest.raises(ValidationError) as exc_info:
        CustomerCreate(**base_payload)
    assert error_msg in str(exc_info.value)


# --- 3. EMAIL SANITIZATION TESTS ---


def test_email_sanitization_logic():
    """Verifies the BeforeValidator cleanly strips padding spaces and downcases email domains."""
    payload = {"first_name": "John", "last_name": "Doe", "email": "  JOHNDOE@company.COM   "}
    schema = CustomerCreate(**payload)
    assert schema.email == "johndoe@company.com"


# --- 4. RESPONSE & ORM MODEL MAPPING TESTS ---


def test_customer_response_serialization():
    """Verifies CustomerResponse populates with native validation transformations intact."""
    ws_id = uuid.uuid4()
    cust_id = uuid.uuid4()
    now = datetime.now(UTC)

    payload = {
        "id": cust_id,
        "workspace_id": ws_id,
        "first_name": "bobby",
        "last_name": "tables",
        "email": "BOBBY@TEST.COM",
        "created_at": now,
        "updated_at": now,
    }

    schema = CustomerResponse(**payload)
    assert schema.id == cust_id
    assert schema.workspace_id == ws_id
    assert schema.first_name == "Bobby"
    assert schema.email == "bobby@test.com"


def test_customer_response_from_orm_attributes():
    """Verifies validation translation works seamlessly when pulling values from standard database objects."""

    class MockCustomerORM:
        def __init__(self):
            self.id = uuid.uuid4()
            self.workspace_id = uuid.uuid4()
            self.first_name = "test"
            self.last_name = "user"
            self.email = "TEST@USER.COM"
            self.created_at = datetime.now(UTC)
            self.updated_at = datetime.now(UTC)

    mock_obj = MockCustomerORM()
    schema = CustomerResponse.model_validate(mock_obj)

    assert schema.id == mock_obj.id
    assert schema.first_name == "Test"
    assert schema.email == "test@user.com"


# --- 5. PAGINATION TESTS ---


def test_customer_paginated_response_success():
    """Verifies list payloads and integer totals bind correctly inside response wrappers."""
    ws_id = uuid.uuid4()
    now = datetime.now(UTC)

    item = {
        "id": uuid.uuid4(),
        "workspace_id": ws_id,
        "first_name": "Jane",
        "last_name": "Doe",
        "email": "jane@test.com",
        "created_at": now,
        "updated_at": now,
    }

    payload = {"items": [item], "total": 1}

    schema = CustomerPaginatedResponse(**payload)
    assert schema.total == 1
    assert len(schema.items) == 1
    assert schema.items[0].first_name == "Jane"


# --- 6. CUSTOMER UPDATE PAYLOAD TESTS ---


def test_customer_update_success():
    """Verifies a full valid update payload initializes successfully."""
    payload = {"first_name": "clark", "last_name": "kent", "email": "  CLARK@DAILYPLANET.COM "}
    schema = CustomerUpdate(**payload)
    assert schema.first_name == "Clark"
    assert schema.email == "clark@dailyplanet.com"


def test_customer_update_requires_fields_by_inheritance():
    """
    Verifies that CustomerUpdate currently expects all base fields (like email)
    because it inherits directly from CustomerBase without modifications.
    """
    payload = {"first_name": "Bruce", "last_name": "Wayne"}
    with pytest.raises(ValidationError) as exc_info:
        CustomerUpdate(**payload)

    assert "Field required" in str(exc_info.value)
    assert "email" in str(exc_info.value)


def test_customer_update_validation_rules_apply():
    """Verifies that custom validations (like the number check) still trigger on updates."""
    payload = {"first_name": "Tony44", "last_name": "Stark", "email": "tony@stark.com"}
    with pytest.raises(CustomerNameMustNotContainNumbersError):
        CustomerUpdate(**payload)
