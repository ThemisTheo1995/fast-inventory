import uuid

import pytest

from src.erp.api.modules.customer.exceptions import (
    CustomerEmailExistsError,
    CustomerNotFoundError,
)
from src.erp.api.modules.customer.models import Customer
from src.erp.api.modules.customer.schemas import CustomerCreate
from src.erp.api.modules.customer.service import CustomerService


def test_create_customer_success(db_session, seed_workspace):
    service = CustomerService(db_session)
    payload = CustomerCreate(first_name="Alex", last_name="Jones", email="alex@test.com")

    customer = service.create_customer(seed_workspace, payload)
    assert customer.id is not None
    assert customer.first_name == "Alex"
    assert customer.workspace_id == seed_workspace


def test_create_customer_duplicate_email_fails(db_session, seed_workspace, active_customer):
    service = CustomerService(db_session)
    payload = CustomerCreate(first_name="Duplicate", last_name="User", email=active_customer.email)

    with pytest.raises(CustomerEmailExistsError):
        service.create_customer(seed_workspace, payload)


def test_create_customer_cross_tenant_email_allowed(db_session, alt_workspace, active_customer):
    """Ensures two separate workspaces can use the same customer email address."""
    service = CustomerService(db_session)
    payload = CustomerCreate(first_name="TenantTwo", last_name="User", email=active_customer.email)

    cross_customer = service.create_customer(alt_workspace, payload)
    assert cross_customer.workspace_id == alt_workspace


def test_create_customer_restores_soft_deleted(db_session, seed_workspace, active_customer):
    service = CustomerService(db_session)
    service.delete_customer(seed_workspace, active_customer.id)

    payload = CustomerCreate(first_name="Jane", last_name="Updated", email=active_customer.email)
    restored = service.create_customer(seed_workspace, payload)

    assert restored.id == active_customer.id
    assert restored.is_deleted is False
    assert restored.last_name == "Updated"


def test_get_customers_pagination_and_search(db_session, seed_workspace):
    service = CustomerService(db_session)

    names = ["Alpha", "Bravo", "Charlie", "Delta", "Echo"]
    for name in names:
        db_session.add(
            Customer(
                id=uuid.uuid4(),
                workspace_id=seed_workspace,
                first_name=name,
                last_name="Test",
                email=f"{name.lower()}@test.com",
            )
        )
    db_session.flush()

    res = service.get_customers(seed_workspace, page=1, limit=2)
    assert len(res.items) == 2
    assert res.total == 5

    search_res = service.get_customers(seed_workspace, search="Charlie")
    assert len(search_res.items) == 1
    assert search_res.items[0].first_name == "Charlie"


def test_get_customer_tenant_isolation(db_session, alt_workspace, active_customer):
    service = CustomerService(db_session)
    with pytest.raises(CustomerNotFoundError):
        service.get_customer(alt_workspace, active_customer.id)
