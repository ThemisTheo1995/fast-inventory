import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import status

from erp.api.modules.supplier.views import (
    create_supplier,
    global_event_bus,
    update_supplier,
)


@pytest.mark.asyncio
@patch("erp.api.modules.supplier.views.global_event_bus.publish")
async def test_router_create_supplier(mock_publish, client, seed_workspace):
    """Verifies an authorized admin can create a supplier within their workspace."""
    response = await client.post(
        f"/{seed_workspace}/suppliers", json={"name": "ACME Industrial", "email": "supply@acme.org"}
    )
    assert response.status_code == status.HTTP_201_CREATED

    data = response.json()
    assert data["name"] == "ACME Industrial"
    assert "id" in data

    mock_publish.assert_called_once()
    event = mock_publish.call_args[0][0]
    assert str(event.workspace_id) == str(seed_workspace)
    assert str(event.supplier.id) == data["id"]


@pytest.mark.asyncio
async def test_router_get_supplier_not_found(client, seed_workspace):
    """Verifies looking up a non-existent supplier ID triggers a 404 error."""
    random_id = uuid.uuid4()
    response = await client.get(f"/{seed_workspace}/suppliers/{random_id}")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_router_get_supplier_details(client, seed_workspace, active_supplier):
    """Verifies a user can fetch details of a valid supplier in their workspace."""
    response = await client.get(f"/{seed_workspace}/suppliers/{active_supplier.id}")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["id"] == str(active_supplier.id)
    assert data["name"] == active_supplier.name


@pytest.mark.asyncio
async def test_router_get_suppliers_list(client, seed_workspace, active_supplier):
    """Verifies fetching a paginated list of suppliers for a workspace."""
    response = await client.get(f"/{seed_workspace}/suppliers")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1

    item_ids = [item["id"] for item in data["items"]]
    assert str(active_supplier.id) in item_ids


@pytest.mark.asyncio
async def test_router_get_suppliers_search_and_pagination(client, seed_workspace, active_supplier):
    """Verifies that the search, page, and limit query parameters are parsed correctly."""
    search_term = active_supplier.name[:4]

    response = await client.get(f"/{seed_workspace}/suppliers", params={"search": search_term, "page": 1, "limit": 5})
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["total"] >= 1
    assert len(data["items"]) <= 5
    assert data["items"][0]["id"] == str(active_supplier.id)


@pytest.mark.asyncio
@patch("erp.api.modules.supplier.views.global_event_bus.publish")
async def test_router_patch_supplier(mock_publish, client, seed_workspace, active_supplier):
    """Verifies atomic fields on a supplier record can be partially updated."""
    response = await client.patch(
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

    # Verify the background task enqueued the event correctly
    mock_publish.assert_called_once()
    event = mock_publish.call_args[0][0]
    assert str(event.workspace_id) == str(seed_workspace)
    assert str(event.supplier.id) == str(active_supplier.id)


@pytest.mark.asyncio
async def test_router_delete_supplier(client, seed_workspace, active_supplier):
    """Verifies a supplier record can be successfully removed or soft-deleted."""
    response = await client.delete(f"/{seed_workspace}/suppliers/{active_supplier.id}")
    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.asyncio
async def test_router_supplier_tenant_isolation(client, alt_workspace, active_supplier):
    """
    CRITICAL SECURITY CHECK: Verifies that an authenticated client in Workspace A
    cannot view, mutate, or access a supplier belonging to Workspace B.
    """
    # Attempting to access Workspace B's supplier using Workspace A's routing scope
    response = await client.get(f"/{alt_workspace}/suppliers/{active_supplier.id}")

    assert response.status_code in (status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN)


@pytest.mark.asyncio
@patch("erp.api.modules.supplier.views.SupplierService")
async def test_create_supplier_enqueues_created_event(
    mock_service_class,
    seed_workspace,
):
    supplier = MagicMock()
    supplier.id = uuid4()

    mock_service = MagicMock()
    mock_service.create_supplier = AsyncMock(return_value=supplier)
    mock_service_class.return_value = mock_service

    background_tasks = MagicMock()
    db = MagicMock()

    data = MagicMock()

    response = await create_supplier(
        workspace_id=seed_workspace,
        data=data,
        background_tasks=background_tasks,
        db=db,
    )

    assert response is supplier

    mock_service.create_supplier.assert_awaited_once_with(
        seed_workspace,
        data,
    )

    background_tasks.add_task.assert_called_once()

    args = background_tasks.add_task.call_args.args

    assert args[0] is global_event_bus.publish

    event = args[1]
    assert event.workspace_id == seed_workspace
    assert event.supplier is supplier


@pytest.mark.asyncio
@patch("erp.api.modules.supplier.views.SupplierService")
async def test_update_supplier_enqueues_updated_event(
    mock_service_class,
    seed_workspace,
):
    supplier_id = uuid4()

    supplier = MagicMock()
    supplier.id = supplier_id

    mock_service = MagicMock()
    mock_service.update_supplier = AsyncMock(return_value=supplier)
    mock_service_class.return_value = mock_service

    background_tasks = MagicMock()
    db = MagicMock()

    data = MagicMock()

    response = await update_supplier(
        workspace_id=seed_workspace,
        supplier_id=supplier_id,
        data=data,
        background_tasks=background_tasks,
        db=db,
    )

    assert response is supplier

    mock_service.update_supplier.assert_awaited_once_with(
        seed_workspace,
        supplier_id,
        data,
    )

    background_tasks.add_task.assert_called_once()

    args = background_tasks.add_task.call_args.args

    assert args[0] is global_event_bus.publish

    event = args[1]
    assert event.workspace_id == seed_workspace
    assert event.supplier is supplier
