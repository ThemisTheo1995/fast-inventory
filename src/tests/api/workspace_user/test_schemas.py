import pytest
from pydantic import ValidationError

from erp.api.workspace_user.enums import (
    InvitationStatusEnum,
    WorkspaceRoleEnum,
)
from erp.api.workspace_user.exceptions import (
    InvalidNameError,
    NameTooShortError,
)
from erp.api.workspace_user.schemas import (
    UserResponse,
    UserUpdateRequest,
    WorkspaceUserInviteRequest,
    WorkspaceUserResponse,
    WorkspaceUserUpdateRequest,
)

# ---------------------------------------------------------------------------
# WorkspaceUserInviteRequest
# ---------------------------------------------------------------------------


def test_workspace_user_invite_request_valid():
    result = WorkspaceUserInviteRequest(
        email="person@example.com",
        role="MEMBER",
    )

    assert result.email == "person@example.com"
    assert result.role == "MEMBER"


def test_workspace_user_invite_request_rejects_invalid_email():
    with pytest.raises(ValidationError):
        WorkspaceUserInviteRequest(
            email="not-an-email",
            role="MEMBER",
        )


def test_workspace_user_invite_request_requires_email_and_role():
    with pytest.raises(ValidationError):
        WorkspaceUserInviteRequest(email="person@example.com")


# ---------------------------------------------------------------------------
# WorkspaceUserUpdateRequest
# ---------------------------------------------------------------------------


def test_workspace_user_update_request_valid():
    result = WorkspaceUserUpdateRequest(
        is_deleted=True,
        role=WorkspaceRoleEnum.FULL_ADMIN,
        status=InvitationStatusEnum.PENDING.value,
    )

    assert result.is_deleted is True
    assert result.role == WorkspaceRoleEnum.FULL_ADMIN
    assert result.status == InvitationStatusEnum.PENDING.value


def test_workspace_user_update_request_allows_omitted_fields():
    result = WorkspaceUserUpdateRequest()

    assert result.is_deleted is None
    assert result.role is None
    assert result.status is None


def test_workspace_user_update_request_rejects_invalid_role():
    with pytest.raises(ValidationError):
        WorkspaceUserUpdateRequest(role="NOT_A_VALID_ROLE")


# ---------------------------------------------------------------------------
# WorkspaceUserResponse
# ---------------------------------------------------------------------------


def test_workspace_user_response_valid():
    result = WorkspaceUserResponse(
        id="12345678-1234-5678-1234-567812345678",
        name="Test Workspace",
        email="person@example.com",
        role=WorkspaceRoleEnum.FULL_ADMIN,
        status=InvitationStatusEnum.ACTIVE.value,
    )

    assert result.name == "Test Workspace"
    assert result.email == "person@example.com"
    assert result.role == WorkspaceRoleEnum.FULL_ADMIN
    assert result.status == InvitationStatusEnum.ACTIVE.value


def test_workspace_user_response_allows_optional_id_and_name():
    result = WorkspaceUserResponse(
        email="person@example.com",
        role=WorkspaceRoleEnum.FULL_ADMIN,
        status=InvitationStatusEnum.ACTIVE.value,
    )

    assert result.id is None
    assert result.name is None


def test_workspace_user_response_rejects_invalid_email():
    with pytest.raises(ValidationError):
        WorkspaceUserResponse(
            email="invalid-email",
            role=WorkspaceRoleEnum.FULL_ADMIN,
            status=InvitationStatusEnum.ACTIVE.value,
        )


# ---------------------------------------------------------------------------
# UserUpdateRequest
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("field", ["first_name", "last_name"])
def test_user_update_request_accepts_valid_name(field):
    result = UserUpdateRequest(**{field: "John"})

    assert getattr(result, field) == "John"


@pytest.mark.parametrize("field", ["first_name", "last_name"])
def test_user_update_request_strips_name_whitespace(field):
    result = UserUpdateRequest(**{field: "  John Smith  "})

    assert getattr(result, field) == "John Smith"


@pytest.mark.parametrize("field", ["first_name", "last_name"])
def test_user_update_request_allows_none(field):
    result = UserUpdateRequest(**{field: None})

    assert getattr(result, field) is None


@pytest.mark.parametrize("field", ["first_name", "last_name"])
def test_user_update_request_rejects_name_without_letters(field):
    with pytest.raises(NameTooShortError):
        UserUpdateRequest(**{field: " -' "})


@pytest.mark.parametrize("field", ["first_name", "last_name"])
@pytest.mark.parametrize(
    "value",
    ["John123", "John@", "John_Smith", "John.Smith"],
)
def test_user_update_request_rejects_invalid_name_characters(field, value):
    with pytest.raises(InvalidNameError):
        UserUpdateRequest(**{field: value})


@pytest.mark.parametrize("field", ["first_name", "last_name"])
@pytest.mark.parametrize("value", [" -' ", "   "])
def test_user_update_request_rejects_names_without_letters(field, value):
    with pytest.raises(NameTooShortError):
        UserUpdateRequest(**{field: value})


@pytest.mark.parametrize("field", ["first_name", "last_name"])
@pytest.mark.parametrize("value", ["Jean-Luc", "O'Connor", "O’Connor"])  # noqa: RUF001
def test_user_update_request_accepts_allowed_punctuation(field, value):
    result = UserUpdateRequest(**{field: value})

    assert getattr(result, field) == value


def test_user_update_request_accepts_unicode_letters():
    result = UserUpdateRequest(
        first_name="José",
        last_name="Müller",
    )

    assert result.first_name == "José"
    assert result.last_name == "Müller"


def test_user_update_request_accepts_empty_update():
    result = UserUpdateRequest()

    assert result.first_name is None
    assert result.last_name is None
    assert result.email is None


def test_user_update_request_accepts_valid_email():
    result = UserUpdateRequest(email="person@example.com")

    assert result.email == "person@example.com"


def test_user_update_request_rejects_invalid_email():
    with pytest.raises(ValidationError):
        UserUpdateRequest(email="invalid-email")


# ---------------------------------------------------------------------------
# UserResponse
# ---------------------------------------------------------------------------


def test_user_response_valid():
    result = UserResponse(
        id="12345678-1234-5678-1234-567812345678",
        email="person@example.com",
        first_name="John",
        last_name="Smith",
    )

    assert result.first_name == "John"
    assert result.last_name == "Smith"
    assert result.email == "person@example.com"


def test_user_response_allows_none_names():
    result = UserResponse(
        id="12345678-1234-5678-1234-567812345678",
        email="person@example.com",
        first_name=None,
        last_name=None,
    )

    assert result.first_name is None
    assert result.last_name is None


def test_user_response_rejects_invalid_email():
    with pytest.raises(ValidationError):
        UserResponse(
            id="12345678-1234-5678-1234-567812345678",
            email="invalid-email",
            first_name="John",
            last_name="Smith",
        )
