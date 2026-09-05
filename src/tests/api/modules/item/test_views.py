import uuid

import pytest
from fastapi import status

# ==============================================================================
# ITEM ROUTER TESTS
# ==============================================================================


@pytest.mark.asyncio
async def test_router_create_item(client, seed_workspace):
    """Verifies an authorized admin can create an item within their workspace."""
    response = await client.post(
        f"/{seed_workspace}/items", json={"title": "Industrial Desk", "sku": "FURN-001", "base_price": 45000}
    )
    assert response.status_code == status.HTTP_201_CREATED

    data = response.json()
    assert data["title"] == "Industrial Desk"
    assert data["sku"] == "FURN-001"
    assert "id" in data


@pytest.mark.asyncio
async def test_router_get_item_not_found(client, seed_workspace):
    """Verifies looking up a non-existent item ID triggers a 404 error."""
    random_id = uuid.uuid4()
    response = await client.get(f"/{seed_workspace}/items/{random_id}")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_router_get_item_details(client, seed_workspace, active_item):
    """Verifies a user can fetch details of a valid item in their workspace."""
    response = await client.get(f"/{seed_workspace}/items/{active_item.id}")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["id"] == str(active_item.id)
    assert data["title"] == active_item.title
    assert data["sku"] == active_item.sku


@pytest.mark.asyncio
async def test_router_get_items_list(client, seed_workspace, active_item):
    """Verifies fetching a paginated list of items for a workspace."""
    response = await client.get(f"/{seed_workspace}/items")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1

    item_ids = [item["id"] for item in data["items"]]
    assert str(active_item.id) in item_ids


@pytest.mark.asyncio
async def test_router_get_items_search_and_pagination(client, seed_workspace, active_item):
    """Verifies that the search, page, and limit query parameters are parsed correctly."""
    # Search using a substring of the active item's title
    search_term = active_item.title[:4]

    response = await client.get(f"/{seed_workspace}/items", params={"search": search_term, "page": 1, "limit": 5})
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["total"] >= 1
    assert len(data["items"]) <= 5
    assert data["items"][0]["id"] == str(active_item.id)


@pytest.mark.asyncio
async def test_router_patch_item(client, seed_workspace, active_item):
    """Verifies atomic fields on an item record can be partially updated."""
    response = await client.patch(
        f"/{seed_workspace}/items/{active_item.id}",
        json={
            "title": "Updated Ergonomic Chair",
        },
    )
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["title"] == "Updated Ergonomic Chair"
    # Verify unprovided fields remain intact
    assert data["sku"] == active_item.sku
    assert data["base_price"] == active_item.base_price


@pytest.mark.asyncio
async def test_router_delete_item(client, seed_workspace, active_item):
    """Verifies an item record can be successfully removed or soft-deleted."""
    response = await client.delete(f"/{seed_workspace}/items/{active_item.id}")
    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.asyncio
async def test_router_item_tenant_isolation(client, alt_workspace, active_item):
    """
    CRITICAL SECURITY CHECK: Verifies that an authenticated client in Workspace A
    cannot view, mutate, or access an item belonging to Workspace B.
    """
    # Attempting to access Workspace B's item using Workspace A's routing scope
    response = await client.get(f"/{alt_workspace}/items/{active_item.id}")

    assert response.status_code in (status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN)
