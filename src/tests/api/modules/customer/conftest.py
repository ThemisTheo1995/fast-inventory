import uuid

import pytest

from src.erp.api.modules.customer.models import Customer

# --- CUSTOMER FIXTURES ---


@pytest.fixture
def active_customer(db_session, seed_workspace) -> Customer:
    """Seeds a live customer record attached to the primary workspace."""
    customer = Customer(
        id=uuid.uuid4(),
        workspace_id=seed_workspace,
        first_name="Active",
        last_name="Customer",
        email="active.customer@test.com",
        is_deleted=False,
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    return customer
