import uuid

import pytest
from pydantic import ValidationError

from erp.api.modules.inventory.schemas.transfer import InventoryTransferRequest


def test_inventory_transfer_request_valid_data():
    item_id = uuid.uuid4()
    source_bin_id = uuid.uuid4()
    destination_bin_id = uuid.uuid4()

    transfer = InventoryTransferRequest(
        item_id=item_id,
        source_bin_id=source_bin_id,
        destination_bin_id=destination_bin_id,
        quantity=10,
        notes="Moving stock to picking area",
    )

    assert transfer.item_id == item_id
    assert transfer.source_bin_id == source_bin_id
    assert transfer.destination_bin_id == destination_bin_id
    assert transfer.quantity == 10
    assert transfer.notes == "Moving stock to picking area"


def test_inventory_transfer_request_requires_item_id():
    with pytest.raises(ValidationError):
        InventoryTransferRequest(
            source_bin_id=uuid.uuid4(),
            destination_bin_id=uuid.uuid4(),
            quantity=10,
        )


def test_inventory_transfer_request_requires_source_bin():
    with pytest.raises(ValidationError):
        InventoryTransferRequest(
            item_id=uuid.uuid4(),
            destination_bin_id=uuid.uuid4(),
            quantity=10,
        )


def test_inventory_transfer_request_requires_destination_bin():
    with pytest.raises(ValidationError):
        InventoryTransferRequest(
            item_id=uuid.uuid4(),
            source_bin_id=uuid.uuid4(),
            quantity=10,
        )


@pytest.mark.parametrize(
    "quantity",
    [0, -1, -10],
)
def test_inventory_transfer_request_rejects_non_positive_quantity(quantity):
    with pytest.raises(ValidationError):
        InventoryTransferRequest(
            item_id=uuid.uuid4(),
            source_bin_id=uuid.uuid4(),
            destination_bin_id=uuid.uuid4(),
            quantity=quantity,
        )


def test_inventory_transfer_request_accepts_positive_quantity():
    transfer = InventoryTransferRequest(
        item_id=uuid.uuid4(),
        source_bin_id=uuid.uuid4(),
        destination_bin_id=uuid.uuid4(),
        quantity=1,
    )

    assert transfer.quantity == 1


def test_inventory_transfer_request_notes_are_optional():
    transfer = InventoryTransferRequest(
        item_id=uuid.uuid4(),
        source_bin_id=uuid.uuid4(),
        destination_bin_id=uuid.uuid4(),
        quantity=5,
    )

    assert transfer.notes is None


def test_inventory_transfer_request_rejects_notes_over_255_characters():
    with pytest.raises(ValidationError):
        InventoryTransferRequest(
            item_id=uuid.uuid4(),
            source_bin_id=uuid.uuid4(),
            destination_bin_id=uuid.uuid4(),
            quantity=5,
            notes="x" * 256,
        )


def test_inventory_transfer_request_accepts_notes_of_255_characters():
    notes = "x" * 255

    transfer = InventoryTransferRequest(
        item_id=uuid.uuid4(),
        source_bin_id=uuid.uuid4(),
        destination_bin_id=uuid.uuid4(),
        quantity=5,
        notes=notes,
    )

    assert transfer.notes == notes
