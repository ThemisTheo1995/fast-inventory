import uuid

import pytest

from src.erp.api.modules.customer.exceptions import CustomerEmailExistsError, CustomerNotFoundError
from src.erp.api.modules.customer.schemas import CustomerCreate, CustomerUpdate
from src.erp.api.modules.customer.service import CustomerService

# ==============================================================================
# 1. CREATE CUSTOMER & SOFT-DELETE RESTORATION
# ==============================================================================


def test_create_customer_success(db_session, seed_workspace):
    """Verifies a brand new customer is created successfully."""
    service = CustomerService(db_session)
    data = CustomerCreate(first_name="John", last_name="Doe", email="john.doe@test.com")

    customer = service.create_customer(seed_workspace, data)

    assert customer.id is not None
    assert customer.workspace_id == seed_workspace
    assert customer.first_name == "John"
    assert customer.email == "john.doe@test.com"


def test_create_customer_existing_email_fails(db_session, seed_workspace):
    """Verifies creating a customer with an email that is already active throws an error."""
    service = CustomerService(db_session)
    data = CustomerCreate(first_name="Jane", last_name="Doe", email="jane.doe@test.com")

    service.create_customer(seed_workspace, data)

    # Attempting to create a second active user with the same email
    with pytest.raises(CustomerEmailExistsError):
        service.create_customer(seed_workspace, data)


def test_create_customer_restores_soft_deleted(db_session, seed_workspace):
    """Verifies that creating a customer with an email belonging to a soft-deleted customer restores the record."""
    service = CustomerService(db_session)

    # 1. Create and delete a customer
    data = CustomerCreate(first_name="Old", last_name="Name", email="restore.me@test.com")
    customer = service.create_customer(seed_workspace, data)
    original_id = customer.id
    service.delete_customer(seed_workspace, original_id)

    # Verify it is actually deleted
    with pytest.raises(CustomerNotFoundError):
        service.get_customer(seed_workspace, original_id)

    # 2. Re-create using the same email but new name
    new_data = CustomerCreate(first_name="New", last_name="Identity", email="restore.me@test.com")
    restored_customer = service.create_customer(seed_workspace, new_data)

    # 3. Assert the original record was recycled and updated
    assert restored_customer.id == original_id
    assert restored_customer.is_deleted is False
    assert restored_customer.first_name == "New"
    assert restored_customer.last_name == "Identity"


# ==============================================================================
# 2. GET CUSTOMER (READ & TENANT ISOLATION)
# ==============================================================================


def test_get_customer_success_and_not_found(db_session, seed_workspace, alt_workspace):
    """Verifies retrieving a customer, including tenant isolation checks."""
    service = CustomerService(db_session)
    data = CustomerCreate(first_name="Alice", last_name="Smith", email="alice@test.com")
    customer = service.create_customer(seed_workspace, data)

    # Success
    found = service.get_customer(seed_workspace, customer.id)
    assert found.id == customer.id

    # Not found (random ID)
    with pytest.raises(CustomerNotFoundError):
        service.get_customer(seed_workspace, uuid.uuid4())

    # Not found (Tenant Isolation - Attempting to read seed_workspace customer from alt_workspace)
    with pytest.raises(CustomerNotFoundError):
        service.get_customer(alt_workspace, customer.id)


def test_get_customers_pagination_and_search(db_session, seed_workspace):
    """Verifies fetching list of customers with pagination and wildcard search terms."""
    service = CustomerService(db_session)
    service.create_customer(seed_workspace, CustomerCreate(first_name="Apple", last_name="Inc", email="apple@test.com"))
    service.create_customer(
        seed_workspace, CustomerCreate(first_name="Banana", last_name="Corp", email="banana@test.com")
    )
    service.create_customer(
        seed_workspace, CustomerCreate(first_name="Cherry", last_name="LLC", email="cherry@test.com")
    )

    # Pagination
    res = service.get_customers(seed_workspace, page=1, limit=2)
    assert res.total == 3
    assert len(res.items) == 2

    # Search matches first_name
    res_first = service.get_customers(seed_workspace, search="Apple")
    assert res_first.total == 1
    assert res_first.items[0].first_name == "Apple"

    # Search matches last_name
    res_last = service.get_customers(seed_workspace, search="Corp")
    assert res_last.total == 1
    assert res_last.items[0].first_name == "Banana"

    # Search matches email
    res_email = service.get_customers(seed_workspace, search="cherry@")
    assert res_email.total == 1
    assert res_email.items[0].first_name == "Cherry"


# ==============================================================================
# 3. UPDATE CUSTOMER
# ==============================================================================


def test_update_customer_success_and_email_uniqueness(db_session, seed_workspace):
    """Verifies partial updates and email constraint validation during updates."""
    service = CustomerService(db_session)
    c1 = service.create_customer(
        seed_workspace, CustomerCreate(first_name="Tony", last_name="Stark", email="tony@test.com")
    )
    c2 = service.create_customer(
        seed_workspace, CustomerCreate(first_name="Bruce", last_name="Wayne", email="bruce@test.com")
    )

    # 1. Successful partial update (name only)
    updated_c1 = service.update_customer(seed_workspace, c1.id, CustomerUpdate(first_name="Anthony"))
    assert updated_c1.first_name == "Anthony"
    assert updated_c1.email == "tony@test.com"  # Email remains unchanged

    # 2. Successful email update
    updated_c1 = service.update_customer(seed_workspace, c1.id, CustomerUpdate(email="anthony.stark@test.com"))
    assert updated_c1.email == "anthony.stark@test.com"

    # 3. Prevent updating to an email owned by another active customer
    with pytest.raises(CustomerEmailExistsError):
        service.update_customer(seed_workspace, c1.id, CustomerUpdate(email="bruce@test.com"))

    # 4. Updating a customer to their *own* exact email succeeds (bypasses uniqueness check)
    same_email_update = service.update_customer(seed_workspace, c2.id, CustomerUpdate(email="bruce@test.com"))
    assert same_email_update.email == "bruce@test.com"


# ==============================================================================
# 4. DELETE CUSTOMER
# ==============================================================================


def test_delete_customer_success_and_idempotency(db_session, seed_workspace):
    """Verifies soft-deletion behavior and that double-deletes trigger a Not Found error."""
    service = CustomerService(db_session)
    c1 = service.create_customer(
        seed_workspace, CustomerCreate(first_name="Delete", last_name="Me", email="del@test.com")
    )

    # Delete successfully
    service.delete_customer(seed_workspace, c1.id)

    # Fetching should now fail
    with pytest.raises(CustomerNotFoundError):
        service.get_customer(seed_workspace, c1.id)

    # Attempting to delete a soft-deleted record fails
    with pytest.raises(CustomerNotFoundError):
        service.delete_customer(seed_workspace, c1.id)
