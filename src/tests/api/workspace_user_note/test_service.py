import uuid

import pytest

from erp.api.workspace_user_note.exceptions import WorkspaceUserNoteNotFoundError
from erp.api.workspace_user_note.models import WorkspaceUserNote
from erp.api.workspace_user_note.schemas import (
    WorkspaceUserNoteCreate,
    WorkspaceUserNoteUpdate,
)
from erp.api.workspace_user_note.service import WorkspaceUserNoteService


@pytest.fixture
async def note(db_session, active_workspace_user):
    record = WorkspaceUserNote(
        workspace_user_id=active_workspace_user.id,
        title="Test note",
        content="Test content",
        is_pinned=False,
        color="#ffffff",
    )
    db_session.add(record)
    await db_session.commit()
    await db_session.refresh(record)
    return record


@pytest.mark.asyncio
async def test_create_note_success(db_session, active_workspace_user):
    service = WorkspaceUserNoteService(db_session)

    data = WorkspaceUserNoteCreate(
        title="New note",
        content="Some content",
        is_pinned=True,
        color="#ff0000",
    )

    result = await service.create_note(active_workspace_user.id, data)

    assert result.id is not None
    assert result.workspace_user_id == active_workspace_user.id
    assert result.title == "New note"
    assert result.content == "Some content"
    assert result.is_pinned is True
    assert result.color == "#ff0000"


@pytest.mark.asyncio
async def test_create_note_with_optional_fields_omitted(
    db_session,
    active_workspace_user,
):
    service = WorkspaceUserNoteService(db_session)

    data = WorkspaceUserNoteCreate(content="Content only")

    result = await service.create_note(active_workspace_user.id, data)

    assert result.content == "Content only"
    assert result.title is None
    assert result.color is None
    assert result.is_pinned is False


@pytest.mark.asyncio
async def test_get_note_success(db_session, active_workspace_user, note):
    service = WorkspaceUserNoteService(db_session)

    result = await service.get_note(active_workspace_user.id, note.id)

    assert result.id == note.id
    assert result.title == note.title
    assert result.content == note.content


@pytest.mark.asyncio
async def test_get_note_not_found(db_session, active_workspace_user):
    service = WorkspaceUserNoteService(db_session)

    with pytest.raises(WorkspaceUserNoteNotFoundError):
        await service.get_note(active_workspace_user.id, uuid.uuid4())


@pytest.mark.asyncio
async def test_get_note_wrong_workspace_user(db_session, note):
    service = WorkspaceUserNoteService(db_session)

    with pytest.raises(WorkspaceUserNoteNotFoundError):
        await service.get_note(uuid.uuid4(), note.id)


@pytest.mark.asyncio
async def test_get_note_soft_deleted_not_found(
    db_session,
    active_workspace_user,
    note,
):
    service = WorkspaceUserNoteService(db_session)

    note.soft_delete()
    await db_session.commit()

    with pytest.raises(WorkspaceUserNoteNotFoundError):
        await service.get_note(active_workspace_user.id, note.id)


@pytest.mark.asyncio
async def test_get_notes_returns_only_active_notes(
    db_session,
    active_workspace_user,
):
    service = WorkspaceUserNoteService(db_session)

    active_note = WorkspaceUserNote(
        workspace_user_id=active_workspace_user.id,
        title="Active",
        content="Active content",
    )
    deleted_note = WorkspaceUserNote(
        workspace_user_id=active_workspace_user.id,
        title="Deleted",
        content="Deleted content",
    )

    db_session.add_all([active_note, deleted_note])
    await db_session.flush()

    deleted_note.soft_delete()
    await db_session.commit()

    result = await service.get_notes(active_workspace_user.id)

    returned_ids = [item.id for item in result.items]

    assert active_note.id in returned_ids
    assert deleted_note.id not in returned_ids
    assert result.total == 1


@pytest.mark.asyncio
async def test_get_notes_does_not_return_other_users_notes(
    db_session,
    active_workspace_user,
    another_workspace_user,
):
    service = WorkspaceUserNoteService(db_session)

    other_note = WorkspaceUserNote(
        workspace_user_id=another_workspace_user.id,
        title="Other user",
        content="Private content",
    )

    db_session.add(other_note)
    await db_session.commit()

    result = await service.get_notes(active_workspace_user.id)

    assert result.total == 0
    assert result.items == []


@pytest.mark.asyncio
async def test_get_notes_pagination(
    db_session,
    active_workspace_user,
):
    service = WorkspaceUserNoteService(db_session)

    records = [
        WorkspaceUserNote(
            workspace_user_id=active_workspace_user.id,
            title=f"Note {i}",
            content=f"Content {i}",
        )
        for i in range(5)
    ]

    db_session.add_all(records)
    await db_session.commit()

    page_one = await service.get_notes(
        active_workspace_user.id,
        page=1,
        limit=2,
    )
    page_two = await service.get_notes(
        active_workspace_user.id,
        page=2,
        limit=2,
    )
    page_three = await service.get_notes(
        active_workspace_user.id,
        page=3,
        limit=2,
    )

    assert page_one.total == 5
    assert len(page_one.items) == 2
    assert len(page_two.items) == 2
    assert len(page_three.items) == 1

    page_one_ids = {item.id for item in page_one.items}
    page_two_ids = {item.id for item in page_two.items}

    assert page_one_ids.isdisjoint(page_two_ids)


@pytest.mark.asyncio
async def test_get_notes_pinned_notes_come_first(
    db_session,
    active_workspace_user,
):
    service = WorkspaceUserNoteService(db_session)

    normal_note = WorkspaceUserNote(
        workspace_user_id=active_workspace_user.id,
        title="Normal note",
        content="Normal",
        is_pinned=False,
    )
    pinned_note = WorkspaceUserNote(
        workspace_user_id=active_workspace_user.id,
        title="Pinned note",
        content="Pinned",
        is_pinned=True,
    )

    db_session.add_all([normal_note, pinned_note])
    await db_session.commit()

    result = await service.get_notes(active_workspace_user.id)

    assert result.items[0].is_pinned is True
    assert result.items[0].id == pinned_note.id


@pytest.mark.asyncio
async def test_update_note_success(
    db_session,
    active_workspace_user,
    note,
):
    service = WorkspaceUserNoteService(db_session)

    data = WorkspaceUserNoteUpdate(
        title="Updated title",
        content="Updated content",
        is_pinned=True,
        color="#000000",
    )

    result = await service.update_note(
        active_workspace_user.id,
        note.id,
        data,
    )

    assert result.title == "Updated title"
    assert result.content == "Updated content"
    assert result.is_pinned is True
    assert result.color == "#000000"


@pytest.mark.asyncio
async def test_update_note_partial_update_preserves_other_fields(
    db_session,
    active_workspace_user,
    note,
):
    service = WorkspaceUserNoteService(db_session)

    original_content = note.content
    original_color = note.color
    original_pinned = note.is_pinned

    data = WorkspaceUserNoteUpdate(title="Changed title")

    result = await service.update_note(
        active_workspace_user.id,
        note.id,
        data,
    )

    assert result.title == "Changed title"
    assert result.content == original_content
    assert result.color == original_color
    assert result.is_pinned == original_pinned


@pytest.mark.asyncio
async def test_update_note_can_clear_nullable_fields(
    db_session,
    active_workspace_user,
    note,
):
    service = WorkspaceUserNoteService(db_session)

    data = WorkspaceUserNoteUpdate(
        title=None,
        color=None,
    )

    result = await service.update_note(
        active_workspace_user.id,
        note.id,
        data,
    )

    assert result.title is None
    assert result.color is None


@pytest.mark.asyncio
async def test_update_note_not_found(db_session, active_workspace_user):
    service = WorkspaceUserNoteService(db_session)

    data = WorkspaceUserNoteUpdate(title="Updated")

    with pytest.raises(WorkspaceUserNoteNotFoundError):
        await service.update_note(
            active_workspace_user.id,
            uuid.uuid4(),
            data,
        )


@pytest.mark.asyncio
async def test_update_note_wrong_workspace_user(db_session, note):
    service = WorkspaceUserNoteService(db_session)

    data = WorkspaceUserNoteUpdate(title="Unauthorized update")

    with pytest.raises(WorkspaceUserNoteNotFoundError):
        await service.update_note(
            uuid.uuid4(),
            note.id,
            data,
        )


@pytest.mark.asyncio
async def test_delete_note_soft_deletes_record(
    db_session,
    active_workspace_user,
    note,
):
    service = WorkspaceUserNoteService(db_session)

    await service.delete_note(active_workspace_user.id, note.id)

    await db_session.refresh(note)

    assert note.is_deleted is True

    with pytest.raises(WorkspaceUserNoteNotFoundError):
        await service.get_note(active_workspace_user.id, note.id)


@pytest.mark.asyncio
async def test_delete_note_not_found(db_session, active_workspace_user):
    service = WorkspaceUserNoteService(db_session)

    with pytest.raises(WorkspaceUserNoteNotFoundError):
        await service.delete_note(
            active_workspace_user.id,
            uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_delete_note_wrong_workspace_user(db_session, note):
    service = WorkspaceUserNoteService(db_session)

    with pytest.raises(WorkspaceUserNoteNotFoundError):
        await service.delete_note(uuid.uuid4(), note.id)
