import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.erp.api.modules.customer.exceptions import (
    CustomerEmailExistsError,
    CustomerNotFoundError,
)
from src.erp.api.modules.customer.schemas import CustomerCreate, CustomerUpdate
from src.erp.api.modules.customer.service import CustomerService

# ==============================================================================
# 1. CREATE CUSTOMER & SOFT-DELETE RESTORATION
# ==============================================================================


async def test_create_customer_success(
    db_session: AsyncSession,
    seed_workspace,
) -> None:
    """Verifies a brand new customer is created successfully."""

    service = CustomerService(db_session)

    data = CustomerCreate(
        first_name="John",
        last_name="Doe",
        email="john.doe@test.com",
    )

    customer = await service.create_customer(
        seed_workspace,
        data,
    )

    assert customer.id is not None
    assert customer.workspace_id == seed_workspace
    assert customer.first_name == "John"
    assert customer.email == "john.doe@test.com"


async def test_create_customer_existing_email_fails(
    db_session: AsyncSession,
    seed_workspace,
) -> None:
    """Verifies creating a customer with an active duplicate email fails."""

    service = CustomerService(db_session)

    data = CustomerCreate(
        first_name="Jane",
        last_name="Doe",
        email="jane.doe@test.com",
    )

    await service.create_customer(
        seed_workspace,
        data,
    )

    with pytest.raises(CustomerEmailExistsError):
        await service.create_customer(
            seed_workspace,
            data,
        )


async def test_create_customer_restores_soft_deleted(
    db_session: AsyncSession,
    seed_workspace,
) -> None:
    """Verifies a soft-deleted customer can be restored."""

    service = CustomerService(db_session)

    # Create customer.
    data = CustomerCreate(
        first_name="Old",
        last_name="Name",
        email="restore.me@test.com",
    )

    customer = await service.create_customer(
        seed_workspace,
        data,
    )

    original_id = customer.id

    # Soft delete customer.
    await service.delete_customer(
        seed_workspace,
        original_id,
    )

    # Verify it is no longer accessible.
    with pytest.raises(CustomerNotFoundError):
        await service.get_customer(
            seed_workspace,
            original_id,
        )

    # Re-create using the same email with a new identity.
    new_data = CustomerCreate(
        first_name="New",
        last_name="Identity",
        email="restore.me@test.com",
    )

    restored_customer = await service.create_customer(
        seed_workspace,
        new_data,
    )

    # Verify the original record was restored.
    assert restored_customer.id == original_id
    assert restored_customer.is_deleted is False
    assert restored_customer.first_name == "New"
    assert restored_customer.last_name == "Identity"


# ==============================================================================
# 2. GET CUSTOMER & TENANT ISOLATION
# ==============================================================================


async def test_get_customer_success_and_not_found(
    db_session: AsyncSession,
    seed_workspace,
    alt_workspace,
) -> None:
    """Verifies retrieval and tenant isolation."""

    service = CustomerService(db_session)

    data = CustomerCreate(
        first_name="Alice",
        last_name="Smith",
        email="alice@test.com",
    )

    customer = await service.create_customer(
        seed_workspace,
        data,
    )

    # Successful retrieval.
    found = await service.get_customer(
        seed_workspace,
        customer.id,
    )

    assert found.id == customer.id

    # Random ID should not exist.
    with pytest.raises(CustomerNotFoundError):
        await service.get_customer(
            seed_workspace,
            uuid.uuid4(),
        )

    # Customer from another workspace must not be accessible.
    with pytest.raises(CustomerNotFoundError):
        await service.get_customer(
            alt_workspace,
            customer.id,
        )


async def test_get_customers_pagination_and_search(
    db_session: AsyncSession,
    seed_workspace,
) -> None:
    """Verifies customer pagination and search."""

    service = CustomerService(db_session)

    await service.create_customer(
        seed_workspace,
        CustomerCreate(
            first_name="Apple",
            last_name="Inc",
            email="apple@test.com",
        ),
    )

    await service.create_customer(
        seed_workspace,
        CustomerCreate(
            first_name="Banana",
            last_name="Corp",
            email="banana@test.com",
        ),
    )

    await service.create_customer(
        seed_workspace,
        CustomerCreate(
            first_name="Cherry",
            last_name="LLC",
            email="cherry@test.com",
        ),
    )

    # Pagination.
    result = await service.get_customers(
        seed_workspace,
        page=1,
        limit=2,
    )

    assert result.total == 3
    assert len(result.items) == 2

    # Search first name.
    result = await service.get_customers(
        seed_workspace,
        search="Apple",
    )

    assert result.total == 1
    assert result.items[0].first_name == "Apple"

    # Search last name.
    result = await service.get_customers(
        seed_workspace,
        search="Corp",
    )

    assert result.total == 1
    assert result.items[0].first_name == "Banana"

    # Search email.
    result = await service.get_customers(
        seed_workspace,
        search="cherry@",
    )

    assert result.total == 1
    assert result.items[0].first_name == "Cherry"


# ==============================================================================
# 3. UPDATE CUSTOMER
# ==============================================================================


async def test_update_customer_success_and_email_uniqueness(
    db_session: AsyncSession,
    seed_workspace,
) -> None:
    """Verifies partial updates and email uniqueness."""

    service = CustomerService(db_session)

    customer_one = await service.create_customer(
        seed_workspace,
        CustomerCreate(
            first_name="Tony",
            last_name="Stark",
            email="tony@test.com",
        ),
    )

    customer_two = await service.create_customer(
        seed_workspace,
        CustomerCreate(
            first_name="Bruce",
            last_name="Wayne",
            email="bruce@test.com",
        ),
    )

    # Successful partial update.
    updated_customer = await service.update_customer(
        seed_workspace,
        customer_one.id,
        CustomerUpdate(first_name="Anthony"),
    )

    assert updated_customer.first_name == "Anthony"
    assert updated_customer.email == "tony@test.com"

    # Successful email update.
    updated_customer = await service.update_customer(
        seed_workspace,
        customer_one.id,
        CustomerUpdate(email="anthony.stark@test.com"),
    )

    assert updated_customer.email == "anthony.stark@test.com"

    # Cannot use another active customer's email.
    with pytest.raises(CustomerEmailExistsError):
        await service.update_customer(
            seed_workspace,
            customer_one.id,
            CustomerUpdate(email="bruce@test.com"),
        )

    # Updating to the customer's existing email is allowed.
    same_email_update = await service.update_customer(
        seed_workspace,
        customer_two.id,
        CustomerUpdate(email="bruce@test.com"),
    )

    assert same_email_update.email == "bruce@test.com"


# ==============================================================================
# 4. DELETE CUSTOMER
# ==============================================================================


async def test_delete_customer_success_and_idempotency(
    db_session: AsyncSession,
    seed_workspace,
) -> None:
    """Verifies soft deletion and double-delete behavior."""

    service = CustomerService(db_session)

    customer = await service.create_customer(
        seed_workspace,
        CustomerCreate(
            first_name="Delete",
            last_name="Me",
            email="del@test.com",
        ),
    )

    # Delete successfully.
    await service.delete_customer(
        seed_workspace,
        customer.id,
    )

    # Deleted customer should no longer be accessible.
    with pytest.raises(CustomerNotFoundError):
        await service.get_customer(
            seed_workspace,
            customer.id,
        )

    # Deleting an already deleted customer should fail.
    with pytest.raises(CustomerNotFoundError):
        await service.delete_customer(
            seed_workspace,
            customer.id,
        )
