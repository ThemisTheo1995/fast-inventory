import uuid

import pytest
from pydantic import ValidationError

from src.erp.api.workspace.schemas import (
    WorkspaceCreate,
    WorkspaceResponse,
    WorkspaceUpdate,
)

# ============================================================================
# WorkspaceCreate Tests
# ============================================================================


def test_workspace_create_valid():
    """Verifies successful creation with valid required fields."""
    data = {"name": "Acme Corp", "email": "contact@acme.com"}
    schema = WorkspaceCreate(**data)

    assert schema.name == "Acme Corp"
    assert schema.email == "contact@acme.com"


@pytest.mark.parametrize(
    "invalid_data, missing_field",
    [
        ({"email": "contact@acme.com"}, "name"),
        ({"name": "Acme Corp"}, "email"),
    ],
)
def test_workspace_create_missing_required_fields(invalid_data, missing_field):
    """Verifies validation failure when required fields are missing."""
    with pytest.raises(ValidationError) as exc_info:
        WorkspaceCreate(**invalid_data)

    errors = exc_info.value.errors()
    assert any(err["loc"][0] == missing_field for err in errors)


def test_workspace_create_invalid_email():
    """Verifies validation failure for invalid email formatting."""
    with pytest.raises(ValidationError) as exc_info:
        WorkspaceCreate(name="Acme Corp", email="invalid-email-string")

    assert exc_info.value.errors()[0]["loc"][0] == "email"


# ============================================================================
# WorkspaceUpdate Tests
# ============================================================================


def test_workspace_update_empty_instantiation():
    """Verifies WorkspaceUpdate can be instantiated with all fields set to None by default."""
    schema = WorkspaceUpdate()

    assert schema.name is None
    assert schema.email is None
    assert schema.phone_number is None
    assert schema.country is None
    assert schema.city is None
    assert schema.address_line1 is None
    assert schema.address_line2 is None
    assert schema.postal_code is None


def test_workspace_update_valid_all_fields():
    """Verifies WorkspaceUpdate accepts valid data across all fields."""
    data = {
        "name": "Updated Corp",
        "email": "updated@acme.com",
        "phone_number": "+14155552671",
        "country": "United States",
        "city": "San Francisco",
        "address_line1": "123 Market St",
        "address_line2": "Suite 400",
        "postal_code": "94105",
    }
    schema = WorkspaceUpdate(**data)

    for key, value in data.items():
        assert getattr(schema, key) == value


@pytest.mark.parametrize(
    "valid_phone",
    [
        None,
        "+14155552671",
        "14155552671",
        "+442071234567",
        "+123",
        "+123456789012345",  # Maximum 15 E.164 digits
    ],
)
def test_workspace_update_phone_number_valid(valid_phone):
    """Verifies E.164 compliant phone numbers and None pass validation."""
    schema = WorkspaceUpdate(phone_number=valid_phone)
    assert schema.phone_number == valid_phone


@pytest.mark.parametrize(
    "invalid_phone",
    [
        "invalid",
        "+0123456789",  # Cannot start with 0 after optional +
        "0123456789",  # Cannot start with 0
        "+1234567890123456",  # Exceeds E.164 15-digit maximum
        "123-456-7890",  # Hyphens not allowed
        "(123) 456-7890",  # Parentheses not allowed
        "",  # Empty string
    ],
)
def test_workspace_update_phone_number_invalid(invalid_phone):
    """Verifies custom field validator rejects non-E.164 phone numbers."""
    with pytest.raises(ValidationError) as exc_info:
        WorkspaceUpdate(phone_number=invalid_phone)

    errors = exc_info.value.errors()
    assert errors[0]["loc"][0] == "phone_number"
    assert "Invalid phone number format" in errors[0]["msg"]


@pytest.mark.parametrize(
    "field_name, max_len",
    [
        ("name", 255),
        ("country", 100),
        ("city", 100),
        ("address_line1", 255),
        ("address_line2", 255),
        ("postal_code", 20),
    ],
)
def test_workspace_update_max_length_constraints(field_name, max_len):
    """Verifies max length Field constraints on string attributes."""
    valid_value = "a" * max_len
    overflow_value = "a" * (max_len + 1)

    # Valid length boundary check
    valid_schema = WorkspaceUpdate(**{field_name: valid_value})
    assert getattr(valid_schema, field_name) == valid_value

    # Exceeding length boundary check
    with pytest.raises(ValidationError) as exc_info:
        WorkspaceUpdate(**{field_name: overflow_value})

    assert exc_info.value.errors()[0]["loc"][0] == field_name


# ============================================================================
# WorkspaceResponse Tests
# ============================================================================


def test_workspace_response_valid():
    """Verifies WorkspaceResponse instantiates with mandatory and optional attributes."""
    workspace_id = uuid.uuid4()
    data = {
        "id": workspace_id,
        "name": "Acme Corp",
        "email": "info@acme.com",
    }
    schema = WorkspaceResponse(**data)

    assert schema.id == workspace_id
    assert schema.name == "Acme Corp"
    assert schema.email == "info@acme.com"
    assert schema.phone_number is None


def test_workspace_response_from_attributes():
    """Verifies ORM object mapping capability via `from_attributes=True`."""

    class MockORMWorkspace:
        def __init__(self):
            self.id = uuid.uuid4()
            self.name = "ORM Workspace"
            self.email = "orm@acme.com"
            self.phone_number = "+14155552671"
            self.country = "USA"
            self.city = "Austin"
            self.address_line1 = "100 Congress Ave"
            self.address_line2 = None
            self.postal_code = "78701"

    orm_obj = MockORMWorkspace()
    schema = WorkspaceResponse.model_validate(orm_obj)

    assert schema.id == orm_obj.id
    assert schema.name == orm_obj.name
    assert schema.email == orm_obj.email
    assert schema.postal_code == "78701"


def test_workspace_response_missing_required():
    """Verifies validation failure when missing required `id` or `name`."""
    with pytest.raises(ValidationError) as exc_info:
        WorkspaceResponse(name="Missing ID")

    assert exc_info.value.errors()[0]["loc"][0] == "id"
