import uuid
from decimal import Decimal

from erp.api.workspace.models import Workspace
from erp.integrations.ebay.items.enums import EbayItemStatus
from erp.integrations.ebay.items.models import EbayItem
from erp.integrations.ebay.items.repository import EbayItemRepository
from erp.integrations.ebay.items.schemas import EbayCreateItem

# ============================================================================
# REPOSITORY TESTS
# ============================================================================


def test_create_item_happy_path(db_session):
    """
    HAPPY PATH:
    A valid EbayCreateItem payload with a real, active workspace_id
    should cleanly save to the database, commit, and return the populated EbayItem instance.
    """
    repo = EbayItemRepository(db_session)

    # Setup pre-requisite workspace record to satisfy FK constraint
    workspace = Workspace(name="Ebay Global Workspace", email="ebay-channel@test.com")
    db_session.add(workspace)
    db_session.flush()  # Generates workspace.id dynamically

    # Build payload passing the workspace_id natively
    payload = EbayCreateItem(
        workspace_id=workspace.id,
        external_id="ebay_112233445566",
        sku="EB-M1-GOLD",
        title="Vintage Gold Mechanical Watch",
        description="A pristine condition 1970s automatic mechanical watch.",
        price=Decimal("249.99"),
        currency="USD",
        quantity=5,
        status=EbayItemStatus.DRAFT,
        images=["https://example.com/watch1.jpg", "https://example.com/watch2.jpg"]
    )

    # Act
    created_item = repo.create(payload)

    # Assert
    assert created_item is not None
    assert isinstance(created_item, EbayItem)
    assert created_item.workspace_id == workspace.id
    assert created_item.external_id == "ebay_112233445566"
    assert created_item.price == Decimal("249.99")
    assert created_item.images == ["https://example.com/watch1.jpg", "https://example.com/watch2.jpg"]


def test_create_item_exception_unique_constraint_violation(db_session):
    """
    EXCEPTION PATH:
    Attempting to create an item that shares an identical (workspace_id, external_id)
    combination with an existing row must trigger an IntegrityError, safely roll back,
    and return None.
    """
    repo = EbayItemRepository(db_session)

    workspace = Workspace(name="Ebay Conflict Workspace", email="conflict@test.com")
    db_session.add(workspace)
    db_session.flush()
    existing_item = EbayItem(
        workspace_id=workspace.id,
        external_id="ebay_duplicate_id",
        sku="ORIGINAL-SKU",
        title="Original Entry",
        description="Existing item description.",
        price=Decimal("100.00"),
        currency="USD",
        quantity=1
    )
    db_session.add(existing_item)
    db_session.flush()

    duplicate_payload = EbayCreateItem(
        workspace_id=workspace.id,
        external_id="ebay_duplicate_id",
        sku="NEW-SKU",
        title="Duplicate Entry Attempt",
        description="Should get rolled back.",
        price=Decimal("150.00"),
        currency="USD"
    )

    # Act
    result = repo.create(duplicate_payload)

    # Assert
    assert result is None


def test_create_item_exception_foreign_key_violation(db_session):
    """
    EXCEPTION PATH:
    If a payload contains a structurally valid UUID for workspace_id, but that workspace
    does not actually exist in the database, the ForeignKey constraint will fail.
    The repository must safely catch this IntegrityError and return None.
    """
    repo = EbayItemRepository(db_session)
    non_existent_workspace_id = uuid.uuid4()
    bad_payload = EbayCreateItem(
        workspace_id=non_existent_workspace_id,
        external_id="ebay_orphan_id",
        sku="ORPHAN-SKU",
        title="Orphaned Item",
        description="No parent workspace.",
        price=Decimal("19.99"),
        currency="USD"
    )

    # Act
    result = repo.create(bad_payload)

    # Assert
    assert result is None


def test_create_item_edge_case_minimal_fields(db_session):
    """
    Validates that the repository engine behaves correctly when optional schema properties
    fall back to their structural defaults (sku = None, images = []).
    """
    repo = EbayItemRepository(db_session)

    workspace = Workspace(name="Minimalist Workspace", email="minimal@test.com")
    db_session.add(workspace)
    db_session.flush()

    minimal_payload = EbayCreateItem(
        workspace_id=workspace.id,
        external_id="ebay_minimal_99",
        sku=None,         # Explicitly null
        images=[],        # Empty array list
        title="Minimal Item",
        description="Stripped down payload tracking.",
        price=Decimal("5.00"),
        currency="USD"
    )

    # Act
    minimal_item = repo.create(minimal_payload)

    # Assert
    assert minimal_item is not None
    assert minimal_item.sku is None
    assert minimal_item.images == []
    assert minimal_item.quantity == 0
