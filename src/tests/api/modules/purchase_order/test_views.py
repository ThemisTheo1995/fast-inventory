import uuid

from fastapi import status
from fastapi.testclient import TestClient

# =======================================================
# 1. PURCHASE ORDER (HEADER) TESTS
# =======================================================


def test_router_create_purchase_order_success(client: TestClient, seed_workspace, active_supplier):
    """Verifies creating a purchase order with valid nested lines returns 201 Created."""
    payload = {
        "po_number": "PO-TEST-001",
        "supplier_id": str(active_supplier.id),
        "status": "DRAFT",
        "purchase_order_lines": [
            {"item_id": None, "quantity": 10, "unit_cost": 150},
            {"item_id": None, "quantity": 5, "unit_cost": 300},
        ],
    }

    response = client.post(f"/{seed_workspace}/purchase-orders", json=payload)

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["po_number"] == "PO-TEST-001"
    assert data["status"] == "DRAFT"
    assert data["supplier_id"] == str(active_supplier.id)
    assert len(data["purchase_order_lines"]) == 2
    assert "total_amount" in data


def test_router_create_purchase_order_empty_lines(client: TestClient, seed_workspace, active_supplier):
    """Verifies creating a purchase order with an empty lines array works."""
    payload = {
        "po_number": "PO-TEST-EMPTY",
        "supplier_id": str(active_supplier.id),
        "purchase_order_lines": [],
    }

    response = client.post(f"/{seed_workspace}/purchase-orders", json=payload)

    assert response.status_code == status.HTTP_201_CREATED
    assert len(response.json()["purchase_order_lines"]) == 0


def test_router_create_purchase_order_validation_error(client: TestClient, seed_workspace):
    """Verifies omitting mandatory fields (po_number) triggers a 422 Validation Error."""
    payload = {
        "status": "DRAFT",
        "purchase_order_lines": [],
    }

    response = client.post(f"/{seed_workspace}/purchase-orders", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert "po_number" in response.text


# --- Get Purchase Orders (List & Pagination) ---


def test_router_get_purchase_orders_success(client: TestClient, seed_workspace, active_purchase_order):
    """Verifies fetching the paginated list of purchase orders returns 200 OK."""
    response = client.get(f"/{seed_workspace}/purchase-orders")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) >= 1
    assert data["items"][0]["id"] == str(active_purchase_order.id)


def test_router_get_purchase_orders_with_pagination_and_search(
    client: TestClient,
    seed_workspace,
    active_purchase_order,  # noqa
):
    """Verifies pagination and search query parameters bind correctly to the endpoint."""
    response = client.get(f"/{seed_workspace}/purchase-orders?search=PO-FIXTURE&page=1&limit=5")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "items" in data
    assert "total" in data


def test_router_get_purchase_orders_invalid_pagination(client: TestClient, seed_workspace):
    """Verifies that invalid pagination types trigger 422."""
    response = client.get(f"/{seed_workspace}/purchase-orders?page=not-a-number")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# --- Get Single Purchase Order ---


def test_router_get_purchase_order_success(client: TestClient, seed_workspace, active_purchase_order):
    """Verifies fetching an existing purchase order by ID returns 200 OK."""
    response = client.get(f"/{seed_workspace}/purchase-orders/{active_purchase_order.id}")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == str(active_purchase_order.id)


def test_router_get_purchase_order_not_found(client: TestClient, seed_workspace):
    """Verifies fetching a non-existent purchase order returns 404 Not Found."""
    fake_id = uuid.uuid4()
    response = client.get(f"/{seed_workspace}/purchase-orders/{fake_id}")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_router_get_purchase_order_invalid_uuid(client: TestClient, seed_workspace):
    """Verifies passing a malformed UUID in the path returns 422 Unprocessable Content."""
    response = client.get(f"/{seed_workspace}/purchase-orders/this-is-not-a-uuid")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# --- Update Purchase Order ---


def test_router_patch_purchase_order_success(client: TestClient, seed_workspace, active_purchase_order):
    """Verifies partial updates to a purchase order return 200 OK and reflect changes."""
    payload = {"po_number": "PO-UPDATED-NUM"}
    response = client.patch(f"/{seed_workspace}/purchase-orders/{active_purchase_order.id}", json=payload)

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["po_number"] == "PO-UPDATED-NUM"


def test_router_patch_purchase_order_not_found(client: TestClient, seed_workspace):
    """Verifies patching a non-existent purchase order returns 404 Not Found."""
    payload = {"po_number": "PO-NEW-NAME"}
    response = client.patch(f"/{seed_workspace}/purchase-orders/{uuid.uuid4()}", json=payload)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_router_patch_purchase_order_validation_error(client: TestClient, seed_workspace, active_purchase_order):
    """Verifies patching with constraint-violating data returns 422."""
    payload = {"po_number": "X" * 150}
    response = client.patch(f"/{seed_workspace}/purchase-orders/{active_purchase_order.id}", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# --- Delete Purchase Order ---


def test_router_delete_purchase_order_success(client: TestClient, seed_workspace, active_purchase_order):
    """Verifies deleting an existing purchase order returns 204 No Content."""
    response = client.delete(f"/{seed_workspace}/purchase-orders/{active_purchase_order.id}")
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Re-verify fetching directly returns a 404
    get_resp = client.get(f"/{seed_workspace}/purchase-orders/{active_purchase_order.id}")
    assert get_resp.status_code == status.HTTP_404_NOT_FOUND


def test_router_delete_purchase_order_not_found(client: TestClient, seed_workspace):
    """Verifies attempting to delete a non-existent purchase order returns 404 Not Found."""
    response = client.delete(f"/{seed_workspace}/purchase-orders/{uuid.uuid4()}")
    assert response.status_code == status.HTTP_404_NOT_FOUND


# =======================================================
# 2. PURCHASE ORDER LINES TESTS
# =======================================================

# --- Add Line ---


def test_router_add_purchase_order_line_success(client: TestClient, seed_workspace, active_purchase_order):
    """Verifies adding a line to an existing purchase order returns 201 Created."""
    payload = {"item_id": None, "quantity": 3, "unit_cost": 500}

    response = client.post(f"/{seed_workspace}/purchase-orders/{active_purchase_order.id}/lines", json=payload)

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["quantity"] == 3
    assert data["unit_cost"] == 500
    assert data["purchase_order_id"] == str(active_purchase_order.id)


def test_router_add_purchase_order_line_po_not_found(client: TestClient, seed_workspace):
    """Verifies adding a line to a non-existent purchase order returns 404 Not Found."""
    payload = {"quantity": 1, "unit_cost": 100}
    response = client.post(f"/{seed_workspace}/purchase-orders/{uuid.uuid4()}/lines", json=payload)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_router_add_purchase_order_line_invalid_data(client: TestClient, seed_workspace, active_purchase_order):
    """Verifies adding a line with negative quantity triggers 422."""
    payload = {"quantity": -10, "unit_cost": 100}
    response = client.post(f"/{seed_workspace}/purchase-orders/{active_purchase_order.id}/lines", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# --- Update Line ---


def test_router_update_purchase_order_line_success(
    client: TestClient, seed_workspace, active_purchase_order, active_purchase_order_line
):
    """Verifies updating an existing purchase order line returns 200 OK and reflects changes."""
    payload = {"quantity": 99, "unit_cost": 999}

    response = client.patch(
        f"/{seed_workspace}/purchase-orders/{active_purchase_order.id}/lines/{active_purchase_order_line.id}",
        json=payload,
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["quantity"] == 99
    assert response.json()["unit_cost"] == 999


def test_router_update_purchase_order_line_not_found(client: TestClient, seed_workspace, active_purchase_order):
    """Verifies patching a non-existent line ID returns 404 Not Found."""
    payload = {"quantity": 10, "unit_cost": 10}
    response = client.patch(
        f"/{seed_workspace}/purchase-orders/{active_purchase_order.id}/lines/{uuid.uuid4()}", json=payload
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_router_update_purchase_order_line_wrong_parent(client: TestClient, seed_workspace, active_purchase_order_line):
    """Verifies updating a line using the WRONG purchase_order_id in the URL returns 404."""
    wrong_po_id = uuid.uuid4()
    payload = {"quantity": 10, "unit_cost": 10}

    response = client.patch(
        f"/{seed_workspace}/purchase-orders/{wrong_po_id}/lines/{active_purchase_order_line.id}", json=payload
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


# --- Delete Line ---


def test_router_delete_purchase_order_line_success(
    client: TestClient, seed_workspace, active_purchase_order, active_purchase_order_line
):
    """Verifies deleting an existing line returns 204 No Content."""
    response = client.delete(
        f"/{seed_workspace}/purchase-orders/{active_purchase_order.id}/lines/{active_purchase_order_line.id}"
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Fetch the parent order to ensure the line is actually gone
    get_resp = client.get(f"/{seed_workspace}/purchase-orders/{active_purchase_order.id}")
    assert get_resp.status_code == status.HTTP_200_OK

    lines = get_resp.json().get("purchase_order_lines", [])
    assert not any(line["id"] == str(active_purchase_order_line.id) for line in lines)


def test_router_delete_purchase_order_line_not_found(client: TestClient, seed_workspace, active_purchase_order):
    """Verifies attempting to delete a non-existent line returns 404 Not Found."""
    response = client.delete(f"/{seed_workspace}/purchase-orders/{active_purchase_order.id}/lines/{uuid.uuid4()}")
    assert response.status_code == status.HTTP_404_NOT_FOUND
