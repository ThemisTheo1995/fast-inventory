import pytest

from erp.api.workspace_user_note.models import WorkspaceUserNote


@pytest.mark.asyncio
async def test_workspace_user_note_create_and_persist(
    db_session,
    active_workspace_user,
):
    note = WorkspaceUserNote(
        workspace_user_id=active_workspace_user.id,
        title="Model test",
        content="Testing persistence",
        is_pinned=True,
        color="#123456",
    )

    db_session.add(note)
    await db_session.commit()
    await db_session.refresh(note)

    assert note.id is not None
    assert note.workspace_user_id == active_workspace_user.id
    assert note.title == "Model test"
    assert note.content == "Testing persistence"
    assert note.is_pinned is True
    assert note.color == "#123456"


@pytest.mark.asyncio
async def test_workspace_user_note_optional_fields(
    db_session,
    active_workspace_user,
):
    note = WorkspaceUserNote(
        workspace_user_id=active_workspace_user.id,
        content="Content only",
    )

    db_session.add(note)
    await db_session.commit()
    await db_session.refresh(note)

    assert note.title is None
    assert note.color is None
    assert note.is_pinned is False


@pytest.mark.asyncio
async def test_workspace_user_note_soft_delete(
    db_session,
    active_workspace_user,
):
    note = WorkspaceUserNote(
        workspace_user_id=active_workspace_user.id,
        content="Delete me",
    )

    db_session.add(note)
    await db_session.commit()

    note.soft_delete()
    await db_session.commit()
    await db_session.refresh(note)

    assert note.is_deleted is True


@pytest.mark.asyncio
async def test_workspace_user_note_workspace_user_relationship(
    db_session,
    active_workspace_user,
):
    note = WorkspaceUserNote(
        workspace_user_id=active_workspace_user.id,
        content="Relationship test",
    )

    db_session.add(note)
    await db_session.commit()
    await db_session.refresh(note)

    assert note.workspace_user_id == active_workspace_user.id
