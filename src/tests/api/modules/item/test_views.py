import uuid

import pytest
from fastapi import status

# ==============================================================================
# ITEM ROUTER TESTS
# ==============================================================================


# ------------------------------------------------------------------------------
# CREATE
# ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_router_create_item(client, seed_workspace):
    """An authorized user can create an item."""
    response = await client.post(
        f"/{seed_workspace}/items",
        json={
            "title": "Industrial Desk",
            "sku": f"FURN-{uuid.uuid4().hex[:8]}",
            "base_price": 45000,
        },
    )

    assert response.status_code == status.HTTP_201_CREATED

    data = response.json()
    assert data["title"] == "Industrial Desk"
    assert data["base_price"] == 45000
    assert data["quantity_on_order"] == 0
    assert data["quantity_allocated"] == 0
    assert data["total_quantity_on_hand"] == 0
    assert data["barcode_id"] is not None
    assert "id" in data


@pytest.mark.asyncio
async def test_router_create_item_uses_default_base_price(client, seed_workspace):
    """Omitting base_price uses the schema default of zero."""
    response = await client.post(
        f"/{seed_workspace}/items",
        json={
            "title": "Default Price Item",
            "sku": f"DEFAULT-{uuid.uuid4().hex[:8]}",
        },
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["base_price"] == 0


@pytest.mark.asyncio
async def test_router_create_item_missing_title(client, seed_workspace):
    """Title is required."""
    response = await client.post(
        f"/{seed_workspace}/items",
        json={"sku": f"NO-TITLE-{uuid.uuid4().hex[:8]}"},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.asyncio
async def test_router_create_item_missing_sku(client, seed_workspace):
    """SKU is required."""
    response = await client.post(
        f"/{seed_workspace}/items",
        json={"title": "Item Without SKU"},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.asyncio
async def test_router_create_item_empty_title(client, seed_workspace):
    """An empty title is rejected."""
    response = await client.post(
        f"/{seed_workspace}/items",
        json={
            "title": "   ",
            "sku": f"EMPTY-TITLE-{uuid.uuid4().hex[:8]}",
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.asyncio
async def test_router_create_item_empty_sku(client, seed_workspace):
    """An empty SKU is rejected."""
    response = await client.post(
        f"/{seed_workspace}/items",
        json={
            "title": "Item With Empty SKU",
            "sku": "   ",
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.asyncio
async def test_router_create_item_negative_base_price(client, seed_workspace):
    """A negative base price is rejected."""
    response = await client.post(
        f"/{seed_workspace}/items",
        json={
            "title": "Negative Price Item",
            "sku": f"NEG-{uuid.uuid4().hex[:8]}",
            "base_price": -100,
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.asyncio
async def test_router_create_item_duplicate_sku(client, seed_workspace, active_item):
    """A duplicate SKU in the same workspace is rejected."""
    response = await client.post(
        f"/{seed_workspace}/items",
        json={
            "title": "Duplicate SKU Item",
            "sku": active_item.sku,
            "base_price": 100,
        },
    )

    assert response.status_code == status.HTTP_409_CONFLICT


# ------------------------------------------------------------------------------
# GET ONE
# ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_router_get_item_not_found(client, seed_workspace):
    """A nonexistent item returns 404."""
    response = await client.get(f"/{seed_workspace}/items/{uuid.uuid4()}")

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_router_get_item_details(client, seed_workspace, active_item):
    """An existing item can be retrieved."""
    item_id = active_item.id
    expected_title = active_item.title
    expected_sku = active_item.sku

    response = await client.get(f"/{seed_workspace}/items/{item_id}")

    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["id"] == str(item_id)
    assert data["title"] == expected_title
    assert data["sku"] == expected_sku


@pytest.mark.asyncio
async def test_router_get_item_deleted_returns_404(
    client,
    seed_workspace,
    active_item,
):
    """A soft-deleted item cannot be retrieved through the active-item endpoint."""
    item_id = active_item.id

    delete_response = await client.delete(f"/{seed_workspace}/items/{item_id}")
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT

    response = await client.get(f"/{seed_workspace}/items/{item_id}")

    assert response.status_code == status.HTTP_404_NOT_FOUND


# ------------------------------------------------------------------------------
# GET LIST
# ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_router_get_items_list(client, seed_workspace, active_item):
    """The item list returns a paginated response."""
    item_id = active_item.id

    response = await client.get(f"/{seed_workspace}/items")

    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "limit" in data
    assert "filters" in data

    assert data["total"] >= 1
    assert str(item_id) in [item["id"] for item in data["items"]]


@pytest.mark.asyncio
async def test_router_get_items_search_by_title(
    client,
    seed_workspace,
    active_item,
):
    """The search parameter matches item titles."""
    item_id = active_item.id
    search_term = active_item.title[:4]

    response = await client.get(
        f"/{seed_workspace}/items",
        params={"search": search_term},
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    item_ids = [item["id"] for item in data["items"]]

    assert str(item_id) in item_ids


@pytest.mark.asyncio
async def test_router_get_items_search_by_sku(
    client,
    seed_workspace,
    active_item,
):
    """The search parameter matches item SKUs."""
    item_id = active_item.id
    search_term = active_item.sku[:4]

    response = await client.get(
        f"/{seed_workspace}/items",
        params={"search": search_term},
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    item_ids = [item["id"] for item in data["items"]]

    assert str(item_id) in item_ids


@pytest.mark.asyncio
async def test_router_get_items_search_no_results(client, seed_workspace):
    """A search with no matches returns an empty result."""
    response = await client.get(
        f"/{seed_workspace}/items",
        params={"search": f"NO-MATCH-{uuid.uuid4().hex}"},
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_router_get_items_pagination(
    client,
    seed_workspace,
):
    """Page and limit parameters are applied."""
    response = await client.get(
        f"/{seed_workspace}/items",
        params={
            "page": 1,
            "limit": 5,
        },
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["page"] == 1
    assert data["limit"] == 5
    assert len(data["items"]) <= 5


@pytest.mark.asyncio
async def test_router_get_items_second_page(
    client,
    seed_workspace,
):
    """The second page is accepted and returned correctly."""
    response = await client.get(
        f"/{seed_workspace}/items",
        params={
            "page": 2,
            "limit": 5,
        },
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["page"] == 2
    assert data["limit"] == 5
    assert len(data["items"]) <= 5


# ------------------------------------------------------------------------------
# UPDATE
# ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_router_patch_item(
    client,
    seed_workspace,
    active_item,
):
    """An item can be partially updated."""
    item_id = active_item.id
    original_sku = active_item.sku
    original_price = active_item.base_price

    response = await client.patch(
        f"/{seed_workspace}/items/{item_id}",
        json={"title": "Updated Ergonomic Chair"},
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["title"] == "Updated Ergonomic Chair"
    assert data["sku"] == original_sku
    assert data["base_price"] == original_price


@pytest.mark.asyncio
async def test_router_patch_item_sku(
    client,
    seed_workspace,
    active_item,
):
    """Updating the SKU succeeds and generates a new barcode identifier."""
    item_id = active_item.id
    new_sku = f"UPDATED-{uuid.uuid4().hex[:8]}"

    response = await client.patch(
        f"/{seed_workspace}/items/{item_id}",
        json={"sku": new_sku},
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["sku"] == new_sku
    assert data["barcode_id"] == f"{seed_workspace}_{new_sku}"


@pytest.mark.asyncio
async def test_router_patch_item_base_price(
    client,
    seed_workspace,
    active_item,
):
    """The base price can be updated independently."""
    response = await client.patch(
        f"/{seed_workspace}/items/{active_item.id}",
        json={"base_price": 2500},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["base_price"] == 2500


@pytest.mark.asyncio
async def test_router_patch_item_negative_base_price(
    client,
    seed_workspace,
    active_item,
):
    """A negative base price is rejected."""
    response = await client.patch(
        f"/{seed_workspace}/items/{active_item.id}",
        json={"base_price": -10},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.asyncio
async def test_router_patch_item_null_title(
    client,
    seed_workspace,
    active_item,
):
    """An explicitly null title is rejected."""
    response = await client.patch(
        f"/{seed_workspace}/items/{active_item.id}",
        json={"title": None},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.asyncio
async def test_router_patch_item_not_found(client, seed_workspace):
    """Updating a nonexistent item returns 404."""
    response = await client.patch(
        f"/{seed_workspace}/items/{uuid.uuid4()}",
        json={"title": "Does Not Exist"},
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_router_patch_item_duplicate_sku(
    client,
    seed_workspace,
    active_item,
    db_session,
):
    """An SKU already used by another item in the workspace is rejected."""
    from erp.api.modules.item.models import Item

    another_item = Item(
        workspace_id=seed_workspace,
        title="Another Item",
        sku=f"OTHER-{uuid.uuid4().hex[:8]}",
        base_price=100,
        is_deleted=False,
    )
    db_session.add(another_item)
    await db_session.commit()

    response = await client.patch(
        f"/{seed_workspace}/items/{active_item.id}",
        json={"sku": another_item.sku},
    )

    assert response.status_code == status.HTTP_409_CONFLICT


# ------------------------------------------------------------------------------
# DELETE
# ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_router_delete_item(
    client,
    seed_workspace,
    active_item,
):
    """An item can be soft-deleted."""
    response = await client.delete(f"/{seed_workspace}/items/{active_item.id}")

    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.asyncio
async def test_router_delete_item_not_found(client, seed_workspace):
    """Deleting a nonexistent item returns 404."""
    response = await client.delete(f"/{seed_workspace}/items/{uuid.uuid4()}")

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_router_delete_item_twice(
    client,
    seed_workspace,
    active_item,
):
    """Deleting an already deleted item returns 404."""
    item_id = active_item.id

    first_response = await client.delete(f"/{seed_workspace}/items/{item_id}")
    assert first_response.status_code == status.HTTP_204_NO_CONTENT

    second_response = await client.delete(f"/{seed_workspace}/items/{item_id}")
    assert second_response.status_code == status.HTTP_404_NOT_FOUND


# ------------------------------------------------------------------------------
# WORKSPACE ISOLATION
# ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_router_item_tenant_isolation(
    client,
    alt_workspace,
    active_item,
):
    """A workspace cannot access another workspace's item."""
    response = await client.get(f"/{alt_workspace}/items/{active_item.id}")

    assert response.status_code in (
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
    )


@pytest.mark.asyncio
async def test_router_item_tenant_isolation_update(
    client,
    alt_workspace,
    active_item,
):
    """A workspace cannot update another workspace's item."""
    response = await client.patch(
        f"/{alt_workspace}/items/{active_item.id}",
        json={"title": "Unauthorized Update"},
    )

    assert response.status_code in (
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
    )


@pytest.mark.asyncio
async def test_router_item_tenant_isolation_delete(
    client,
    alt_workspace,
    active_item,
):
    """A workspace cannot delete another workspace's item."""
    response = await client.delete(f"/{alt_workspace}/items/{active_item.id}")

    assert response.status_code in (
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
    )
