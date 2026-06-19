import pytest

from erp.api.workspace.enums import InvitationStatusEnum, WorkspaceRoleEnum

# ============================================================================
# WORKSPACE ROLE ENUM TESTS
# ============================================================================


@pytest.mark.parametrize(
    "role, expected_label",
    [
        (WorkspaceRoleEnum.FULL_ADMIN, "Full Admin"),
        (WorkspaceRoleEnum.EDIT_ONLY, "Edit Only"),
        (WorkspaceRoleEnum.READ_ONLY, "Read Only"),
    ]
)
def test_workspace_role_enum_labels(role, expected_label):
    """
    Every defined workspace role must map clean to its respective
    human-readable visual label string.
    """
    assert role.label == expected_label


# ============================================================================
# INVITATION STATUS ENUM TESTS
# ============================================================================

@pytest.mark.parametrize(
    "status, expected_label",
    [
        (InvitationStatusEnum.ACTIVE, "Active"),
        (InvitationStatusEnum.PENDING, "Pending"),
    ]
)
def test_invitation_status_enum_labels(status, expected_label):
    """
    Every legal system invitation lifecycle state must accurately resolve
    to its human-readable display status.
    """
    assert status.label == expected_label
