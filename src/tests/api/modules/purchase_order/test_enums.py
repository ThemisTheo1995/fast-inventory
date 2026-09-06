import pytest

from erp.api.modules.purchase_order.enums import POStatusEnum


@pytest.mark.parametrize(
    "status, expected_label",
    [
        (POStatusEnum.DRAFT, "Draft"),
        (POStatusEnum.SENT, "Sent"),
        (POStatusEnum.IN_TRANSIT, "In Transit"),
        (POStatusEnum.RECEIVED, "Received"),
        (POStatusEnum.RETURNED, "Returned"),
        (POStatusEnum.CANCELLED, "Cancelled"),
        (POStatusEnum.CLOSED, "Closed"),
    ],
)
def test_po_status_label(status, expected_label):
    assert status.label == expected_label
