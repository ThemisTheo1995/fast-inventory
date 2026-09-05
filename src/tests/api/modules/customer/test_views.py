import uuid

import pytest
from fastapi import status


@pytest.mark.asyncio
async def test_router_create_customer(client, seed_workspace):
    """Verifies customer creation and background task registration."""
    response = await client.post(
        f"/{seed_workspace}/customers",
        json={"first_name": "Route", "last_name": "Test", "email": "router@test.com"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["first_name"] == "Route"
    assert data["last_name"] == "Test"
    assert "id" in data


@pytest.mark.asyncio
async def test_router_get_customer_not_found(client, seed_workspace):
    """Verifies looking up a non-existent customer ID triggers a 404 error."""
    response = await client.get(f"/{seed_workspace}/customers/{uuid.uuid4()}")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_router_get_customer_details(client, seed_workspace, active_customer):
    """Verifies a user can fetch details of a valid customer in their workspace."""
    response = await client.get(f"/{seed_workspace}/customers/{active_customer.id}")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["id"] == str(active_customer.id)
    assert data["first_name"] == active_customer.first_name
    assert data["last_name"] == active_customer.last_name


@pytest.mark.asyncio
async def test_router_get_customers_list(client, seed_workspace, active_customer):
    """Verifies fetching a paginated list of customers for a workspace."""
    response = await client.get(f"/{seed_workspace}/customers")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1
    assert any(item["id"] == str(active_customer.id) for item in data["items"])


@pytest.mark.asyncio
async def test_router_get_customers_search_and_pagination(client, seed_workspace, active_customer):
    """Verifies that the search, page, and limit query parameters are parsed correctly."""
    response = await client.get(
        f"/{seed_workspace}/customers",
        params={"search": active_customer.first_name[:3], "page": 1, "limit": 5}
    )
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["total"] >= 1
    assert len(data["items"]) <= 5
    assert data["items"][0]["id"] == str(active_customer.id)


@pytest.mark.asyncio
async def test_router_patch_customer(client, seed_workspace, active_customer):
    """Verifies atomic fields on a customer record can be partially updated and triggers background task."""
    response = await client.patch(
        f"/{seed_workspace}/customers/{active_customer.id}",
        json={"first_name": "Updatedname"},
    )
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["first_name"] == "Updatedname"
    assert data["last_name"] == active_customer.last_name
    assert data["email"] == active_customer.email


@pytest.mark.asyncio
async def test_router_delete_customer(client, seed_workspace, active_customer):
    """Verifies a customer record can be successfully removed or soft-deleted."""
    response = await client.delete(f"/{seed_workspace}/customers/{active_customer.id}")
    assert response.status_code == status.HTTP_204_NO_CONTENT

    get_resp = await client.get(f"/{seed_workspace}/customers/{active_customer.id}")
    assert get_resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_router_customer_tenant_isolation(client, alt_workspace, active_customer):
    """
    CRITICAL SECURITY CHECK: Verifies that an authenticated client in Workspace A
    cannot view, mutate, or access a customer belonging to Workspace B.
    """
    response = await client.get(f"/{alt_workspace}/customers/{active_customer.id}")
    assert response.status_code == status.HTTP_404_NOT_FOUND
