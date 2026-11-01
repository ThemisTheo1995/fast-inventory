import pytest

from erp.api.search.enums import EntityTypeEnum


@pytest.mark.parametrize(
    "entity_type, expected_value, expected_label",
    [
        (EntityTypeEnum.BIN, "bin", "Bin"),
        (EntityTypeEnum.CUSTOMER, "customer", "Customer"),
        (EntityTypeEnum.SUPPLIER, "supplier", "Supplier"),
        (EntityTypeEnum.ITEM, "item", "Item"),
        (EntityTypeEnum.SELL_ORDER, "sell_order", "Sell Order"),
        (EntityTypeEnum.PURCHASE_ORDER, "purchase_order", "Purchase Order"),
        (EntityTypeEnum.INVENTORY, "inventory", "Inventory"),
        (EntityTypeEnum.STOCK_MOVEMENT, "stock_movement", "Stock Movement"),
    ],
)
def test_entity_type_enum_values_and_labels(
    entity_type,
    expected_value,
    expected_label,
):
    assert entity_type.value == expected_value
    assert entity_type.label == expected_label


def test_entity_type_enum_is_string_enum():
    assert isinstance(EntityTypeEnum.ITEM, str)
    assert EntityTypeEnum.ITEM == "item"


def test_entity_type_enum_label_replaces_underscores():
    assert EntityTypeEnum.STOCK_MOVEMENT.label == "Stock Movement"


def test_entity_type_enum_contains_eight_members():
    assert len(EntityTypeEnum) == 8
