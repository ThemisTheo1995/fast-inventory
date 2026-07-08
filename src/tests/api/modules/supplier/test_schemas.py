import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.erp.api.modules.supplier.schemas import (
    SupplierCreate,
    SupplierPaginatedResponse,
    SupplierResponse,
    SupplierUpdate,
)

# --- 1. EMAIL SANITIZATION & SANITY TESTS ---


def test_supplier_email_sanitization():
    """Verifies the BeforeValidator strips whitespace and downcases the incoming email."""
    payload = {"name": "Acme Corp", "email": "  SupporT@ACME-corp.COM  "}
    schema = SupplierCreate(**payload)
    # The custom BeforeValidator logic should clean this up cleanly
    assert schema.email == "support@acme-corp.com"


def test_supplier_email_handles_none_safely():
    """Verifies that an explicit None or omitted email value is accepted."""
    payload = {"name": "Acme Corp", "email": None}
    schema = SupplierCreate(**payload)
    assert schema.email is None


# --- 2. NAME CONSTRAINT TESTS ---


def test_supplier_name_boundary_valid():
    """Verifies names at exactly the minimum length threshold (2 chars) pass."""
    schema = SupplierCreate(name="AJ", email="aj@test.com")
    assert schema.name == "AJ"


@pytest.mark.parametrize(
    "invalid_name",
    [
        "",  # Length 0
        "A",  # Length 1 (violates min_length=2)
        "X" * 256,  # Length 256 (violates max_length=255)
    ],
)
def test_supplier_name_boundary_invalid(invalid_name):
    """Verifies name lengths outside 2-255 characters trigger validation failures."""
    with pytest.raises(ValidationError) as exc_info:
        SupplierCreate(name=invalid_name, email="test@test.com")

    assert "name" in str(exc_info.value)


# --- 3. CREATE & UPDATE PAYLOAD TESTS ---


def test_supplier_create_missing_required_name():
    """Verifies creating a supplier without a name triggers a validation error."""
    with pytest.raises(ValidationError) as exc_info:
        SupplierCreate(email="missing-name@test.com")

    assert "Field required" in str(exc_info.value)
    assert "name" in str(exc_info.value)


def test_supplier_update_requires_name_by_inheritance():
    """
    Verifies that SupplierUpdate currently expects a name because it inherits
    directly from SupplierBase without modifications.
    """
    with pytest.raises(ValidationError) as exc_info:
        SupplierUpdate(email="patch-test@test.com")

    assert "Field required" in str(exc_info.value)


# --- 4. RESPONSE & ORM MAPPING TESTS ---


def test_supplier_response_serialization():
    """Verifies SupplierResponse accurately constructs with structural tracking IDs."""
    ws_id = uuid.uuid4()
    sup_id = uuid.uuid4()
    now = datetime.now(UTC)

    payload = {
        "id": sup_id,
        "workspace_id": ws_id,
        "name": "Response Logistics",
        "email": "LOGISTICS@test.com",
        "created_at": now,
        "updated_at": now,
    }

    schema = SupplierResponse(**payload)
    assert schema.id == sup_id
    assert schema.workspace_id == ws_id
    assert schema.email == "logistics@test.com"


def test_supplier_response_from_orm_attributes():
    """Verifies standard ORM model mock conversion matches config expectations."""

    class MockSupplierORM:
        def __init__(self):
            self.id = uuid.uuid4()
            self.workspace_id = uuid.uuid4()
            self.name = "Mocked Object Corp"
            self.email = "  Mock@Test.com "
            self.created_at = datetime.now(UTC)
            self.updated_at = datetime.now(UTC)

    mock_obj = MockSupplierORM()

    # Tests from_attributes=True config binding integration
    schema = SupplierResponse.model_validate(mock_obj)
    assert schema.id == mock_obj.id
    assert schema.name == "Mocked Object Corp"
    assert schema.email == "mock@test.com"


# --- 5. PAGINATION SCHEMAS ---


def test_supplier_paginated_response_success():
    """Verifies collection wrapper layouts match structured pagination output arrays."""
    ws_id = uuid.uuid4()
    now = datetime.now(UTC)

    single_item = {
        "id": uuid.uuid4(),
        "workspace_id": ws_id,
        "name": "Bulk Supplier",
        "email": "bulk@test.com",
        "created_at": now,
        "updated_at": now,
    }

    paginated_payload = {"items": [single_item], "total": 1}

    schema = SupplierPaginatedResponse(**paginated_payload)
    assert schema.total == 1
    assert len(schema.items) == 1
    assert schema.items[0].name == "Bulk Supplier"
