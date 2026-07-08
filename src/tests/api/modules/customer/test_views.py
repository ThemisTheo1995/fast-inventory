import uuid

from fastapi import status


def test_router_create_customer(client, seed_workspace):
    # Fixed: workspace_id is now the first element of the URL path layout
    response = client.post(
        f"/{seed_workspace}/customers", json={"first_name": "Route", "last_name": "Test", "email": "router@test.com"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["first_name"] == "Route"


def test_router_get_customer_not_found(client, seed_workspace):
    # Fixed: /{workspace_id}/customers/{customer_id}
    response = client.get(f"/{seed_workspace}/customers/{uuid.uuid4()}")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_router_patch_customer(client, seed_workspace, active_customer):
    # Fixed: /{workspace_id}/customers/{customer_id}
    response = client.patch(
        f"/{seed_workspace}/customers/{active_customer.id}",
        json={"first_name": "Updatedname", "last_name": "Doe", "email": "jane.doe@example.com"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["first_name"] == "Updatedname"


def test_router_delete_customer(client, seed_workspace, active_customer):
    # Fixed: /{workspace_id}/customers/{customer_id}
    print(f"/{seed_workspace}/customers/{active_customer.id}")
    response = client.delete(f"/{seed_workspace}/customers/{active_customer.id}")
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Re-verify fetching directly returns a 404
    get_resp = client.get(f"/{seed_workspace}/customers/{active_customer.id}")
    assert get_resp.status_code == status.HTTP_404_NOT_FOUND
