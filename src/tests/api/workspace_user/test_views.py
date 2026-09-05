import uuid

from fastapi import status

from src.erp.api.workspace_user.enums import WorkspaceRoleEnum


async def test_router_get_workspace_users(client, seed_workspace, active_workspace_user):
    """Verifies retrieval of all users associated with a specific workspace path layout."""
    response = await client.get(f"/{seed_workspace}/workspace-users")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert isinstance(data, list)
    assert len(data) >= 1
    assert any(item["id"] == str(active_workspace_user.id) for item in data)


async def test_router_get_workspace_user_not_found(client, seed_workspace):
    """Verifies fetching a non-existent workspace user returns 404 NOT FOUND."""
    random_id = uuid.uuid4()

    response = await client.get(f"/{seed_workspace}/workspace-users/{random_id}")

    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_router_invite_workspace_user(client, seed_workspace):
    """Verifies an authorized admin can invite a member to their specific workspace route."""
    payload = {
        "email": "invited-collaborator@test.com",
        "first_name": "New",
        "last_name": "Collaborator",
        "role": WorkspaceRoleEnum.EDIT_ONLY,
    }

    response = await client.post(f"/{seed_workspace}/workspace-users/invite", json=payload)

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()

    assert "id" in data
    assert data["role"] == "edit_only"
    assert data["status"] == "pending"


async def test_router_update_workspace_user(client, seed_workspace, target_workspace_user):
    """Verifies altering a workspace user role transitions cleanly via structural routes."""
    payload = {"role": WorkspaceRoleEnum.FULL_ADMIN}

    response = await client.patch(f"/{seed_workspace}/workspace-users/{target_workspace_user.id}", json=payload)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["id"] == str(target_workspace_user.id)
    assert data["role"] == "full_admin"


async def test_router_update_workspace_user_not_found(client, seed_workspace):
    """Verifies modifying a non-existent tracking reference inside a valid workspace gets a 404."""
    random_id = uuid.uuid4()
    payload = {"role": WorkspaceRoleEnum.READ_ONLY}

    response = await client.patch(f"/{seed_workspace}/workspace-users/{random_id}", json=payload)

    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_router_update_workspace_user_unprocessible_no_role_found(client, seed_workspace):
    """Verifies modifying a workspace user with a non-existent role gets a 422."""
    random_id = uuid.uuid4()
    payload = {"role": "NOT_FOUND"}

    response = await client.patch(f"/{seed_workspace}/workspace-users/{random_id}", json=payload)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_router_get_me(client, seed_workspace, active_workspace_user):
    """Verifies retrieval of the currently authenticated user's workspace profile."""
    response = await client.get(f"/{seed_workspace}/me")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["workspace_user_id"] == str(active_workspace_user.id)
    assert data["id"] == str(active_workspace_user.user.id)
    assert data["email"] == active_workspace_user.user.email
    assert data["role"] == active_workspace_user.role


async def test_router_update_me(client, seed_workspace, active_workspace_user):
    """Verifies the currently authenticated user can update their personal details."""
    payload = {"first_name": "UpdatedFirst", "last_name": "UpdatedLast"}

    response = await client.patch(f"/{seed_workspace}/me", json=payload)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["first_name"] == "UpdatedFirst"
    assert data["last_name"] == "UpdatedLast"
    assert data["id"] == str(active_workspace_user.user.id)


async def test_router_get_workspace_user_by_id(client, seed_workspace, target_workspace_user):
    """Verifies retrieving a specific workspace user by their ID."""
    response = await client.get(f"/{seed_workspace}/workspace-users/{target_workspace_user.id}")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["id"] == str(target_workspace_user.id)
    assert "role" in data
    assert "status" in data
