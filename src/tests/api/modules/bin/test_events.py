import uuid
from dataclasses import is_dataclass

from erp.api.modules.bin.events import (
    BinCreatedEvent,
    BinUpdatedEvent,
)


def test_bin_created_event():
    workspace_id = uuid.uuid4()
    bin_obj = object()

    event = BinCreatedEvent(
        workspace_id=workspace_id,
        bin=bin_obj,
    )

    assert event.workspace_id == workspace_id
    assert event.bin is bin_obj


def test_bin_updated_event():
    workspace_id = uuid.uuid4()
    bin_obj = object()

    event = BinUpdatedEvent(
        workspace_id=workspace_id,
        bin=bin_obj,
    )

    assert event.workspace_id == workspace_id
    assert event.bin is bin_obj


def test_bin_created_event_is_dataclass():
    assert is_dataclass(BinCreatedEvent)


def test_bin_updated_event_is_dataclass():
    assert is_dataclass(BinUpdatedEvent)


def test_bin_created_event_is_mutable():
    event = BinCreatedEvent(
        workspace_id=uuid.uuid4(),
        bin=object(),
    )

    new_workspace_id = uuid.uuid4()
    event.workspace_id = new_workspace_id

    assert event.workspace_id == new_workspace_id


def test_bin_updated_event_is_mutable():
    event = BinUpdatedEvent(
        workspace_id=uuid.uuid4(),
        bin=object(),
    )

    new_workspace_id = uuid.uuid4()
    event.workspace_id = new_workspace_id

    assert event.workspace_id == new_workspace_id
