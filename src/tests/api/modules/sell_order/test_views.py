import uuid

from fastapi import status

# =======================================================
# 1. SELL ORDER (HEADER) TESTS
# =======================================================

# --- Create Sell Order ---


def test_router_create_sell_order_success(client, seed_workspace, active_customer):
    """Verifies creating a sell order with valid nested lines returns 201 Created."""
    payload = {
        "so_number": "SO-TEST-001",
        "customer_id": str(active_customer.id),
        "status": "DRAFT",
        "sell_order_lines": [
            {"item_id": None, "quantity": 10, "unit_cost": 150},
            {"item_id": None, "quantity": 5, "unit_cost": 300},
        ],
    }

    response = client.post(f"/{seed_workspace}/sell-orders", json=payload)

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["so_number"] == "SO-TEST-001"
    assert data["status"] == "DRAFT"
    assert data["customer_id"] == str(active_customer.id)
    assert len(data["sell_order_lines"]) == 2
    assert "total_amount" in data


def test_router_create_sell_order_empty_lines(client, seed_workspace):
    """Verifies creating a sell order with an empty lines array works."""
    payload = {"so_number": "SO-TEST-EMPTY", "sell_order_lines": []}

    response = client.post(f"/{seed_workspace}/sell-orders", json=payload)

    assert response.status_code == status.HTTP_201_CREATED
    assert len(response.json()["sell_order_lines"]) == 0


def test_router_create_sell_order_validation_error(client, seed_workspace):
    """Verifies omitting mandatory fields (so_number) triggers a 422 Validation Error."""
    payload = {
        "status": "DRAFT",
        "sell_order_lines": [],
        # Missing so_number
    }

    response = client.post(f"/{seed_workspace}/sell-orders", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert "so_number" in response.text


# --- Get Sell Orders (List & Pagination) ---


def test_router_get_sell_orders_success(client, seed_workspace, active_sell_order):
    """Verifies fetching the paginated list of sell orders returns 200 OK."""
    response = client.get(f"/{seed_workspace}/sell-orders")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) >= 1
    assert data["items"][0]["id"] == str(active_sell_order.id)


def test_router_get_sell_orders_with_pagination_and_search(client, seed_workspace):
    """Verifies pagination and search query parameters bind correctly to the endpoint."""
    response = client.get(f"/{seed_workspace}/sell-orders?search=SO-TEST&page=2&limit=5")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "items" in data
    assert "total" in data


def test_router_get_sell_orders_invalid_pagination(client, seed_workspace):
    """Verifies that invalid pagination types trigger 422."""
    response = client.get(f"/{seed_workspace}/sell-orders?page=not-a-number")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# --- Get Single Sell Order ---


def test_router_get_sell_order_success(client, seed_workspace, active_sell_order):
    """Verifies fetching an existing sell order by ID returns 200 OK."""
    response = client.get(f"/{seed_workspace}/sell-orders/{active_sell_order.id}")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == str(active_sell_order.id)


def test_router_get_sell_order_not_found(client, seed_workspace):
    """Verifies fetching a non-existent sell order returns 404 Not Found."""
    fake_id = uuid.uuid4()
    response = client.get(f"/{seed_workspace}/sell-orders/{fake_id}")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_router_get_sell_order_invalid_uuid(client, seed_workspace):
    """Verifies passing a malformed UUID in the path returns 422 Unprocessable Content."""
    response = client.get(f"/{seed_workspace}/sell-orders/this-is-not-a-uuid")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# --- Update Sell Order ---


def test_router_patch_sell_order_success(client, seed_workspace, active_sell_order):
    """Verifies partial updates to a sell order return 200 OK and reflect changes."""
    payload = {"status": "CONFIRMED"}
    response = client.patch(f"/{seed_workspace}/sell-orders/{active_sell_order.id}", json=payload)

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "CONFIRMED"
    # Ensure other fields weren't wiped out
    assert response.json()["so_number"] == active_sell_order.so_number


def test_router_patch_sell_order_not_found(client, seed_workspace):
    """Verifies patching a non-existent sell order returns 404 Not Found."""
    payload = {"so_number": "SO-NEW-NAME"}
    response = client.patch(f"/{seed_workspace}/sell-orders/{uuid.uuid4()}", json=payload)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_router_patch_sell_order_validation_error(client, seed_workspace, active_sell_order):
    """Verifies patching with constraint-violating data returns 422."""
    payload = {"so_number": "X" * 150}  # Exceeds max length of 100
    response = client.patch(f"/{seed_workspace}/sell-orders/{active_sell_order.id}", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# --- Delete Sell Order ---


def test_router_delete_sell_order_success(client, seed_workspace, active_sell_order):
    """Verifies deleting an existing sell order returns 204 No Content."""
    response = client.delete(f"/{seed_workspace}/sell-orders/{active_sell_order.id}")
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Re-verify fetching directly returns a 404
    get_resp = client.get(f"/{seed_workspace}/sell-orders/{active_sell_order.id}")
    assert get_resp.status_code == status.HTTP_404_NOT_FOUND


def test_router_delete_sell_order_not_found(client, seed_workspace):
    """Verifies attempting to delete a non-existent sell order returns 404 Not Found."""
    response = client.delete(f"/{seed_workspace}/sell-orders/{uuid.uuid4()}")
    assert response.status_code == status.HTTP_404_NOT_FOUND


# =======================================================
# 2. SELL ORDER LINES TESTS
# =======================================================

# --- Add Line ---


def test_router_add_sell_order_line_success(client, seed_workspace, active_sell_order):
    """Verifies adding a line to an existing sell order returns 201 Created."""
    payload = {"item_id": None, "quantity": 3, "unit_cost": 500}

    response = client.post(f"/{seed_workspace}/sell-orders/{active_sell_order.id}/lines", json=payload)

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["quantity"] == 3
    assert data["unit_cost"] == 500
    assert data["sell_order_id"] == str(active_sell_order.id)


def test_router_add_sell_order_line_so_not_found(client, seed_workspace):
    """Verifies adding a line to a non-existent sell order returns 404 Not Found."""
    payload = {"quantity": 1, "unit_cost": 100}
    response = client.post(f"/{seed_workspace}/sell-orders/{uuid.uuid4()}/lines", json=payload)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_router_add_sell_order_line_invalid_data(client, seed_workspace, active_sell_order):
    """Verifies adding a line with negative quantity triggers 422."""
    payload = {"quantity": -10, "unit_cost": 100}
    response = client.post(f"/{seed_workspace}/sell-orders/{active_sell_order.id}/lines", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# --- Update Line ---


def test_router_update_sell_order_line_success(client, seed_workspace, active_sell_order, active_sell_order_line):
    """Verifies updating an existing sell order line returns 200 OK and reflects changes."""
    payload = {"quantity": 99, "unit_cost": 999}

    response = client.patch(
        f"/{seed_workspace}/sell-orders/{active_sell_order.id}/lines/{active_sell_order_line.id}", json=payload
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["quantity"] == 99
    assert response.json()["unit_cost"] == 999


def test_router_update_sell_order_line_not_found(client, seed_workspace, active_sell_order):
    """Verifies patching a non-existent line ID returns 404 Not Found."""
    payload = {"quantity": 10, "unit_cost": 10}
    response = client.patch(f"/{seed_workspace}/sell-orders/{active_sell_order.id}/lines/{uuid.uuid4()}", json=payload)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_router_update_sell_order_line_wrong_parent(client, seed_workspace, active_sell_order_line):
    """Verifies updating a line using the WRONG sell_order_id in the URL returns 404."""
    wrong_so_id = uuid.uuid4()
    payload = {"quantity": 10, "unit_cost": 10}

    response = client.patch(
        f"/{seed_workspace}/sell-orders/{wrong_so_id}/lines/{active_sell_order_line.id}", json=payload
    )
    # The service layer should enforce that the line actually belongs to the given sell_order_id
    assert response.status_code == status.HTTP_404_NOT_FOUND


# --- Delete Line ---


def test_router_delete_sell_order_line_success(client, seed_workspace, active_sell_order, active_sell_order_line):
    """Verifies deleting an existing line returns 204 No Content."""
    response = client.delete(f"/{seed_workspace}/sell-orders/{active_sell_order.id}/lines/{active_sell_order_line.id}")
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Fetch the parent order to ensure the line is actually gone
    get_resp = client.get(f"/{seed_workspace}/sell-orders/{active_sell_order.id}")
    assert get_resp.status_code == status.HTTP_200_OK

    # Check that the line ID is no longer in the order's lines array
    lines = get_resp.json().get("sell_order_lines", [])
    assert not any(line["id"] == str(active_sell_order_line.id) for line in lines)


def test_router_delete_sell_order_line_not_found(client, seed_workspace, active_sell_order):
    """Verifies attempting to delete a non-existent line returns 404 Not Found."""
    response = client.delete(f"/{seed_workspace}/sell-orders/{active_sell_order.id}/lines/{uuid.uuid4()}")
    assert response.status_code == status.HTTP_404_NOT_FOUND
