import uuid

from fastapi import status


def test_router_create_supplier(client, seed_workspace):
    """Verifies an authorized admin can create a supplier within their workspace."""
    response = client.post(f"/{seed_workspace}/suppliers", json={"name": "ACME Industrial", "email": "supply@acme.org"})
    assert response.status_code == status.HTTP_201_CREATED

    data = response.json()
    assert data["name"] == "ACME Industrial"
    assert "id" in data


def test_router_get_supplier_not_found(client, seed_workspace):
    """Verifies looking up a non-existent supplier ID triggers a 404 error."""
    random_id = uuid.uuid4()
    response = client.get(f"/{seed_workspace}/suppliers/{random_id}")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_router_get_supplier_details(client, seed_workspace, active_supplier):
    """Verifies a user can fetch details of a valid supplier in their workspace."""
    response = client.get(f"/{seed_workspace}/suppliers/{active_supplier.id}")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["id"] == str(active_supplier.id)
    assert data["name"] == active_supplier.name


def test_router_get_suppliers_list(client, seed_workspace, active_supplier):
    """Verifies fetching a paginated list of suppliers for a workspace."""
    response = client.get(f"/{seed_workspace}/suppliers")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1

    item_ids = [item["id"] for item in data["items"]]
    assert str(active_supplier.id) in item_ids


def test_router_get_suppliers_search_and_pagination(client, seed_workspace, active_supplier):
    """Verifies that the search, page, and limit query parameters are parsed correctly."""
    search_term = active_supplier.name[:4]

    response = client.get(f"/{seed_workspace}/suppliers", params={"search": search_term, "page": 1, "limit": 5})
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["total"] >= 1
    assert len(data["items"]) <= 5
    assert data["items"][0]["id"] == str(active_supplier.id)


def test_router_patch_supplier(client, seed_workspace, active_supplier):
    """Verifies atomic fields on a supplier record can be partially updated."""
    response = client.patch(
        f"/{seed_workspace}/suppliers/{active_supplier.id}",
        json={
            "name": "Global Logistics Corp",
        },
    )
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["name"] == "Global Logistics Corp"
    # Verify unprovided fields remain intact
    assert data["email"] == "info@globallogistics.com"


def test_router_delete_supplier(client, seed_workspace, active_supplier):
    """Verifies a supplier record can be successfully removed or soft-deleted."""
    response = client.delete(f"/{seed_workspace}/suppliers/{active_supplier.id}")
    assert response.status_code == status.HTTP_204_NO_CONTENT


def test_router_supplier_tenant_isolation(client, alt_workspace, active_supplier):
    """
    CRITICAL SECURITY CHECK: Verifies that an authenticated client in Workspace A
    cannot view, mutate, or access a supplier belonging to Workspace B.
    """
    # Attempting to access Workspace B's supplier using Workspace A's routing scope
    response = client.get(f"/{alt_workspace}/suppliers/{active_supplier.id}")

    assert response.status_code in (status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN)
