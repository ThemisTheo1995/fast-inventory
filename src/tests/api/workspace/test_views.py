import uuid

from fastapi import status


async def test_get_workspace_success(client, seed_workspace):
    """Verifies retrieving workspace details for the active workspace."""
    response = await client.get(f"/{seed_workspace}")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == str(seed_workspace)
    assert data["name"] == "Primary Test Workspace"
    assert data["email"] == f"primary-{seed_workspace}@test.com"


async def test_get_workspace_not_found(client):
    """Verifies retrieving a non-existent workspace returns 404 NOT FOUND."""
    random_id = uuid.uuid4()
    response = await client.get(f"/{random_id}")

    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_update_workspace_success(client, seed_workspace):
    """Verifies updating workspace attributes (name, location, phone)."""
    payload = {
        "name": "Updated Primary Workspace",
        "phone_number": "+14155552671",
        "country": "United States",
        "city": "San Francisco",
    }

    response = await client.patch(f"/{seed_workspace}", json=payload)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == str(seed_workspace)
    assert data["name"] == "Updated Primary Workspace"
    assert data["phone_number"] == "+14155552671"
    assert data["country"] == "United States"
    assert data["city"] == "San Francisco"


async def test_update_workspace_partial(client, seed_workspace):
    """Verifies partial updates keep unmodified fields unchanged."""
    payload = {"city": "Austin"}

    response = await client.patch(f"/{seed_workspace}", json=payload)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["city"] == "Austin"
    assert data["name"] == "Primary Test Workspace"


async def test_update_workspace_invalid_phone_format(client, seed_workspace):
    """Verifies schema validation failure (422) when submitting a non-E.164 phone number."""
    payload = {"phone_number": "invalid-phone"}

    response = await client.patch(f"/{seed_workspace}", json=payload)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_update_workspace_not_found(client):
    """Verifies updating a non-existent workspace returns 404 NOT FOUND."""
    random_id = uuid.uuid4()
    payload = {"name": "Should Not Work"}

    response = await client.patch(f"/{random_id}", json=payload)

    assert response.status_code == status.HTTP_404_NOT_FOUND
