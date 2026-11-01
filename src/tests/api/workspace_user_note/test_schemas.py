import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from erp.api.workspace_user_note.schemas import (
    WorkspaceUserNoteCreate,
    WorkspaceUserNotePaginatedResponse,
    WorkspaceUserNoteResponse,
    WorkspaceUserNoteUpdate,
)


def test_create_note_valid_data():
    data = WorkspaceUserNoteCreate(
        title="My note",
        content="Some content",
        is_pinned=True,
        color="#ffffff",
    )

    assert data.title == "My note"
    assert data.content == "Some content"
    assert data.is_pinned is True
    assert data.color == "#ffffff"


def test_create_note_minimal_data():
    data = WorkspaceUserNoteCreate(content="Content")

    assert data.content == "Content"
    assert data.title is None
    assert data.is_pinned is False
    assert data.color is None


def test_create_note_missing_content():
    with pytest.raises(ValidationError):
        WorkspaceUserNoteCreate(title="Missing content")


def test_create_note_empty_content_is_valid():
    data = WorkspaceUserNoteCreate(content="")

    assert data.content == ""


def test_create_note_title_max_length():
    data = WorkspaceUserNoteCreate(
        title="T" * 255,
        content="Content",
    )

    assert len(data.title) == 255


def test_create_note_title_exceeds_max_length():
    with pytest.raises(ValidationError):
        WorkspaceUserNoteCreate(
            title="T" * 256,
            content="Content",
        )


def test_create_note_color_max_length():
    data = WorkspaceUserNoteCreate(
        content="Content",
        color="C" * 50,
    )

    assert len(data.color) == 50


def test_create_note_color_exceeds_max_length():
    with pytest.raises(ValidationError):
        WorkspaceUserNoteCreate(
            content="Content",
            color="C" * 51,
        )


def test_update_note_partial_data():
    data = WorkspaceUserNoteUpdate(title="Updated")

    assert data.title == "Updated"
    assert data.model_dump(exclude_unset=True) == {
        "title": "Updated",
    }


def test_update_note_empty_data():
    data = WorkspaceUserNoteUpdate()

    assert data.model_dump(exclude_unset=True) == {}


def test_update_note_explicit_null_title():
    data = WorkspaceUserNoteUpdate(title=None)

    assert data.model_dump(exclude_unset=True) == {
        "title": None,
    }


def test_update_note_content_null_currently_allowed():
    """Documents current schema behaviour; content is non-nullable in the DB."""
    data = WorkspaceUserNoteUpdate(content=None)

    assert data.content is None


def test_update_note_is_pinned_null_currently_allowed():
    """Documents current schema behaviour; is_pinned is non-nullable in the DB."""
    data = WorkspaceUserNoteUpdate(is_pinned=None)

    assert data.is_pinned is None


def test_update_note_title_max_length():
    data = WorkspaceUserNoteUpdate(title="T" * 255)

    assert len(data.title) == 255


def test_update_note_title_exceeds_max_length():
    with pytest.raises(ValidationError):
        WorkspaceUserNoteUpdate(title="T" * 256)


def test_response_schema_from_attributes():
    now = datetime.now(UTC)

    class NoteObject:
        id = uuid.uuid4()
        workspace_user_id = uuid.uuid4()
        title = "Test"
        content = "Content"
        is_pinned = True
        color = "#ffffff"
        created_at = now
        updated_at = now

    response = WorkspaceUserNoteResponse.model_validate(NoteObject())

    assert response.title == "Test"
    assert response.content == "Content"
    assert response.is_pinned is True
    assert response.id == NoteObject.id


def test_paginated_response_schema():
    now = datetime.now(UTC)

    note = WorkspaceUserNoteResponse(
        id=uuid.uuid4(),
        workspace_user_id=uuid.uuid4(),
        title="Test",
        content="Content",
        is_pinned=False,
        color=None,
        created_at=now,
        updated_at=now,
    )

    response = WorkspaceUserNotePaginatedResponse(
        items=[note],
        total=1,
    )

    assert response.total == 1
    assert len(response.items) == 1
    assert response.items[0].title == "Test"


def test_paginated_response_empty():
    response = WorkspaceUserNotePaginatedResponse(
        items=[],
        total=0,
    )

    assert response.items == []
    assert response.total == 0
