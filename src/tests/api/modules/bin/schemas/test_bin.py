import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from erp.api.modules.bin.schemas.bin import (
    BinCreate,
    BinResponse,
    BinUpdate,
)


def test_bin_create_normalizes_code_and_zone():
    data = BinCreate(code="  a-01-03  ", zone="  Warehouse A  ")

    assert data.code == "A-01-03"
    assert data.zone == "Warehouse A"


def test_bin_create_empty_zone_becomes_none():
    data = BinCreate(code="A-01", zone="   ")

    assert data.zone is None


@pytest.mark.parametrize(
    "code",
    [
        "",
        "   ",
        "A/01",
        "A@01",
        "A#01",
    ],
)
def test_bin_create_rejects_invalid_code(code):
    with pytest.raises(ValidationError):
        BinCreate(code=code)


def test_bin_create_rejects_code_over_max_length():
    with pytest.raises(ValidationError):
        BinCreate(code="A" * 51)


def test_bin_create_allows_valid_code_characters():
    data = BinCreate(code="A-01_02.03")

    assert data.code == "A-01_02.03"


def test_bin_update_normalizes_code_and_zone():
    data = BinUpdate(code="  b-02  ", zone="  Zone B  ")

    assert data.code == "B-02"
    assert data.zone == "Zone B"


def test_bin_update_allows_omitted_fields():
    data = BinUpdate()

    assert data.model_dump(exclude_unset=True) == {}


def test_bin_update_allows_null_fields():
    data = BinUpdate(code=None, zone=None)

    assert data.code is None
    assert data.zone is None


def test_bin_update_rejects_empty_code():
    with pytest.raises(ValidationError):
        BinUpdate(code="   ")


def test_bin_update_rejects_invalid_code_characters():
    with pytest.raises(ValidationError):
        BinUpdate(code="BIN/01")


def test_bin_response_from_attributes():
    now = datetime.now(UTC)

    class BinObject:
        id = uuid.uuid4()
        workspace_id = uuid.uuid4()
        code = "A-01"
        zone = "Warehouse A"
        created_at = now
        updated_at = now

    response = BinResponse.model_validate(BinObject())

    assert response.id == BinObject.id
    assert response.workspace_id == BinObject.workspace_id
    assert response.code == "A-01"
    assert response.zone == "Warehouse A"
