import uuid

import pytest
from fastapi import status
from httpx import AsyncClient


@pytest.fixture
async def active_note(db_session, active_workspace_user):
    from erp.api.workspace_user_note.models import WorkspaceUserNote

    note = WorkspaceUserNote(
        workspace_user_id=active_workspace_user.id,
        title="Router test note",
        content="Router test content",
        is_pinned=False,
        color="#ffffff",
    )

    db_session.add(note)
    await db_session.commit()
    await db_session.refresh(note)

    return note


# =======================================================
# CREATE
# =======================================================


@pytest.mark.asyncio
async def test_router_create_note_success(
    client: AsyncClient,
    seed_workspace,
):
    payload = {
        "title": "New note",
        "content": "Note content",
        "is_pinned": True,
        "color": "#ff0000",
    }

    response = await client.post(
        f"/{seed_workspace}/notes",
        json=payload,
    )

    assert response.status_code == status.HTTP_201_CREATED

    data = response.json()

    assert data["id"]
    assert data["title"] == "New note"
    assert data["content"] == "Note content"
    assert data["is_pinned"] is True
    assert data["color"] == "#ff0000"


@pytest.mark.asyncio
async def test_router_create_note_minimal_data(
    client: AsyncClient,
    seed_workspace,
):
    response = await client.post(
        f"/{seed_workspace}/notes",
        json={"content": "Content only"},
    )

    assert response.status_code == status.HTTP_201_CREATED

    data = response.json()

    assert data["content"] == "Content only"
    assert data["title"] is None
    assert data["color"] is None
    assert data["is_pinned"] is False


@pytest.mark.asyncio
async def test_router_create_note_missing_content(
    client: AsyncClient,
    seed_workspace,
):
    response = await client.post(
        f"/{seed_workspace}/notes",
        json={"title": "Missing content"},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.asyncio
async def test_router_create_note_title_too_long(
    client: AsyncClient,
    seed_workspace,
):
    response = await client.post(
        f"/{seed_workspace}/notes",
        json={
            "title": "T" * 256,
            "content": "Content",
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.asyncio
async def test_router_create_note_color_too_long(
    client: AsyncClient,
    seed_workspace,
):
    response = await client.post(
        f"/{seed_workspace}/notes",
        json={
            "content": "Content",
            "color": "C" * 51,
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# =======================================================
# LIST
# =======================================================


@pytest.mark.asyncio
async def test_router_get_notes_success(
    client: AsyncClient,
    seed_workspace,
    active_note,
):
    response = await client.get(f"/{seed_workspace}/notes")

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1

    returned_ids = [item["id"] for item in data["items"]]
    assert str(active_note.id) in returned_ids


@pytest.mark.asyncio
async def test_router_get_notes_pagination(
    client: AsyncClient,
    seed_workspace,
):
    response = await client.get(f"/{seed_workspace}/notes?page=1&limit=2")

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert len(data["items"]) <= 2
    assert "total" in data


@pytest.mark.asyncio
async def test_router_get_notes_invalid_page(
    client: AsyncClient,
    seed_workspace,
):
    response = await client.get(f"/{seed_workspace}/notes?page=0")

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.asyncio
async def test_router_get_notes_invalid_limit(
    client: AsyncClient,
    seed_workspace,
):
    response = await client.get(f"/{seed_workspace}/notes?limit=101")

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.asyncio
async def test_router_get_notes_invalid_pagination_type(
    client: AsyncClient,
    seed_workspace,
):
    response = await client.get(f"/{seed_workspace}/notes?page=invalid")

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# =======================================================
# GET ONE
# =======================================================


@pytest.mark.asyncio
async def test_router_get_note_success(
    client: AsyncClient,
    seed_workspace,
    active_note,
):
    response = await client.get(f"/{seed_workspace}/notes/{active_note.id}")

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert data["id"] == str(active_note.id)
    assert data["title"] == active_note.title
    assert data["content"] == active_note.content


@pytest.mark.asyncio
async def test_router_get_note_not_found(
    client: AsyncClient,
    seed_workspace,
):
    response = await client.get(f"/{seed_workspace}/notes/{uuid.uuid4()}")

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_router_get_note_invalid_uuid(
    client: AsyncClient,
    seed_workspace,
):
    response = await client.get(f"/{seed_workspace}/notes/not-a-uuid")

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# =======================================================
# UPDATE
# =======================================================


@pytest.mark.asyncio
async def test_router_update_note_success(
    client: AsyncClient,
    seed_workspace,
    active_note,
):
    payload = {
        "title": "Updated title",
        "content": "Updated content",
        "is_pinned": True,
        "color": "#000000",
    }

    response = await client.patch(
        f"/{seed_workspace}/notes/{active_note.id}",
        json=payload,
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert data["title"] == "Updated title"
    assert data["content"] == "Updated content"
    assert data["is_pinned"] is True
    assert data["color"] == "#000000"


@pytest.mark.asyncio
async def test_router_update_note_partial_update(
    client: AsyncClient,
    seed_workspace,
    active_note,
):
    response = await client.patch(
        f"/{seed_workspace}/notes/{active_note.id}",
        json={"title": "Only title changed"},
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    assert data["title"] == "Only title changed"
    assert data["content"] == active_note.content
    assert data["color"] == active_note.color


@pytest.mark.asyncio
async def test_router_update_note_not_found(
    client: AsyncClient,
    seed_workspace,
):
    response = await client.patch(
        f"/{seed_workspace}/notes/{uuid.uuid4()}",
        json={"title": "Updated"},
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_router_update_note_invalid_uuid(
    client: AsyncClient,
    seed_workspace,
):
    response = await client.patch(
        f"/{seed_workspace}/notes/not-a-uuid",
        json={"title": "Updated"},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.asyncio
async def test_router_update_note_title_too_long(
    client: AsyncClient,
    seed_workspace,
    active_note,
):
    response = await client.patch(
        f"/{seed_workspace}/notes/{active_note.id}",
        json={"title": "T" * 256},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# =======================================================
# DELETE
# =======================================================


@pytest.mark.asyncio
async def test_router_delete_note_success(
    client: AsyncClient,
    seed_workspace,
    active_note,
):
    response = await client.delete(f"/{seed_workspace}/notes/{active_note.id}")

    assert response.status_code == status.HTTP_204_NO_CONTENT

    get_response = await client.get(f"/{seed_workspace}/notes/{active_note.id}")

    assert get_response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_router_delete_note_not_found(
    client: AsyncClient,
    seed_workspace,
):
    response = await client.delete(f"/{seed_workspace}/notes/{uuid.uuid4()}")

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_router_delete_note_invalid_uuid(
    client: AsyncClient,
    seed_workspace,
):
    response = await client.delete(f"/{seed_workspace}/notes/not-a-uuid")

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
