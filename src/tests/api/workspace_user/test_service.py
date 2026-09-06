import uuid

import pytest
from sqlalchemy import select

from erp.api.auth.models import User
from erp.api.workspace.models import Workspace
from erp.api.workspace_user.enums import WorkspaceRoleEnum
from erp.api.workspace_user.exceptions import (
    PrivilegeEscalationBlockedError,
    RankImmunityViolationError,
    SelfEvictionBlockedError,
    SelfModificationBlockedError,
    WorkspaceUserAlreadyInWorkspaceError,
    WorkspaceUserNotFoundError,
)
from erp.api.workspace_user.models import WorkspaceUser
from erp.api.workspace_user.schemas import (
    UserUpdateRequest,
    WorkspaceUserInviteRequest,
    WorkspaceUserResponse,
    WorkspaceUserUpdateRequest,
)
from erp.api.workspace_user.service import WorkspaceUserService

# ============================================================================
# LOOKUP HELPER TESTS (`_get_active_workspace_user`)
# ============================================================================


async def test_get_active_workspace_user_happy_path(db_session):
    """Should return the WorkspaceUser record when it exists."""
    service = WorkspaceUserService(db_session)

    workspace = Workspace(name="WS", email="w@t.com")
    db_session.add(workspace)
    await db_session.flush()

    user = User(
        id=uuid.uuid4(),
        email="lookup_happy@test.com",
        is_deleted=False,
        hashed_password="",
    )
    db_session.add(user)
    await db_session.flush()

    link = WorkspaceUser(
        workspace_id=str(workspace.id),
        user_id=str(user.id),
        role=WorkspaceRoleEnum.EDIT_ONLY,
        status="active",
        is_deleted=False,
    )
    db_session.add(link)
    await db_session.flush()

    result = await service._get_active_workspace_user(str(workspace.id), str(link.id))
    assert result.workspace_id == str(workspace.id)
    assert result.user_id == str(user.id)


async def test_get_active_workspace_user_raises_not_found_if_missing(db_session):
    """Should raise WorkspaceUserNotFoundError if no matching record exists."""
    service = WorkspaceUserService(db_session)
    with pytest.raises(WorkspaceUserNotFoundError):
        await service._get_active_workspace_user(str(uuid.uuid4()), str(uuid.uuid4()))


async def test_get_active_workspace_user_raises_not_found_if_soft_deleted(db_session):
    """Should treat soft-deleted workspace members as non-existent."""
    service = WorkspaceUserService(db_session)

    workspace = Workspace(name="WS", email="w01@t.com")
    db_session.add(workspace)
    await db_session.flush()

    user = User(
        id=uuid.uuid4(),
        email="lookup_soft@test.com",
        is_deleted=False,
        hashed_password="",
    )
    db_session.add(user)
    await db_session.flush()

    link = WorkspaceUser(
        workspace_id=str(workspace.id),
        user_id=str(user.id),
        role=WorkspaceRoleEnum.EDIT_ONLY,
        status="active",
        is_deleted=True,
    )
    db_session.add(link)
    await db_session.flush()

    with pytest.raises(WorkspaceUserNotFoundError):
        await service._get_active_workspace_user(str(workspace.id), str(user.id))


# ============================================================================
# FETCH WORKSPACE USERS TESTS (`get_workspace_users`)
# ============================================================================


async def test_get_workspace_users_happy_path_and_name_formatting(db_session):
    """Should fetch all active members and format full names correctly."""
    service = WorkspaceUserService(db_session)
    workspace = Workspace(name="WS", email="w1@t.com")
    db_session.add(workspace)
    await db_session.flush()

    u1 = User(
        id=uuid.uuid4(),
        email="user1@test.com",
        first_name="John",
        last_name="Doe",
        is_deleted=False,
        hashed_password="",
    )
    l1 = WorkspaceUser(
        workspace_id=str(workspace.id),
        user_id=str(u1.id),
        role=WorkspaceRoleEnum.FULL_ADMIN,
        status="active",
        is_deleted=False,
    )

    u2 = User(
        id=uuid.uuid4(),
        email="user2@test.com",
        first_name="Solo",
        last_name="",
        is_deleted=False,
        hashed_password="",
    )
    l2 = WorkspaceUser(
        workspace_id=str(workspace.id),
        user_id=str(u2.id),
        role="read_only",
        status="pending",
        is_deleted=False,
    )

    db_session.add_all([u1, l1, u2, l2])
    await db_session.flush()

    workspace_users = await service.get_workspace_users(str(workspace.id))

    assert len(workspace_users) == 2
    assert isinstance(workspace_users[0], WorkspaceUserResponse)
    assert isinstance(workspace_users[1], WorkspaceUserResponse)
    assert workspace_users[1].id == l1.id
    assert workspace_users[1].name == "John Doe"

    assert workspace_users[0].id == l2.id
    assert workspace_users[0].name == "Solo"


async def test_get_workspace_users_excludes_soft_deleted_records(db_session):
    """Should ignore workspace links or user records that are soft-deleted."""
    service = WorkspaceUserService(db_session)
    workspace = Workspace(name="WS", email="w2@t.com")
    db_session.add(workspace)
    await db_session.flush()

    u_active = User(
        id=uuid.uuid4(),
        email="active@test.com",
        first_name="A",
        last_name="B",
        is_deleted=False,
        hashed_password="",
    )
    l_active = WorkspaceUser(
        workspace_id=str(workspace.id),
        user_id=str(u_active.id),
        role="read_only",
        status="active",
        is_deleted=False,
    )

    u_del_link = User(
        id=uuid.uuid4(),
        email="dellink@test.com",
        first_name="C",
        last_name="D",
        is_deleted=False,
        hashed_password="",
    )
    l_del_link = WorkspaceUser(
        workspace_id=str(workspace.id),
        user_id=str(u_del_link.id),
        role="read_only",
        status="active",
        is_deleted=True,
    )

    u_del_user = User(
        id=uuid.uuid4(),
        email="deluser@test.com",
        first_name="E",
        last_name="F",
        is_deleted=True,
        hashed_password="",
    )
    l_del_user = WorkspaceUser(
        workspace_id=str(workspace.id),
        user_id=str(u_del_user.id),
        role="read_only",
        status="active",
        is_deleted=False,
    )

    db_session.add_all([u_active, l_active, u_del_link, l_del_link, u_del_user, l_del_user])
    await db_session.flush()

    workspace_users = await service.get_workspace_users(str(workspace.id))
    assert len(workspace_users) == 1
    assert workspace_users[0].id == l_active.id


# ============================================================================
# FETCH WORKSPACE USER SERVICE TESTS (`get_workspace_user`)
# ============================================================================


async def test_service_get_workspace_user_not_found(db_session):
    """Verifies WorkspaceUserService.get_workspace_user raises 404 when ID doesn't exist."""
    service = WorkspaceUserService(db_session)

    with pytest.raises(WorkspaceUserNotFoundError):
        await service.get_workspace_user(uuid.uuid4())


async def test_service_get_workspace_user_happy_path(db_session):
    """Verifies successful retrieval and mapping of a specific workspace user."""
    service = WorkspaceUserService(db_session)
    workspace = Workspace(name="WS_SINGLE", email="single_ws@t.com")
    db_session.add(workspace)
    await db_session.flush()

    user = User(
        id=uuid.uuid4(),
        email="single_target@test.com",
        first_name="Jane",
        last_name="Doe",
        is_deleted=False,
        hashed_password="",
    )
    db_session.add(user)
    await db_session.flush()

    ws_user = WorkspaceUser(
        workspace_id=str(workspace.id),
        user_id=str(user.id),
        role=WorkspaceRoleEnum.EDIT_ONLY,
        status="active",
        is_deleted=False,
    )
    db_session.add(ws_user)
    await db_session.flush()

    result = await service.get_workspace_user(ws_user.id)

    assert result.id == ws_user.id
    assert result.name == "Jane Doe"
    assert result.email == "single_target@test.com"
    assert result.role == WorkspaceRoleEnum.EDIT_ONLY
    assert result.status == "active"


# ============================================================================
# INVITATION SERVICE TESTS (`invite_workspace_user`)
# ============================================================================


async def test_invite_workspace_user_happy_path_new_user(db_session):
    """Should create a fresh User shell and link record on invitation."""
    service = WorkspaceUserService(db_session)
    workspace = Workspace(name="WS", email="w02@t.com")
    db_session.add(workspace)
    await db_session.flush()

    user = User(
        id=uuid.uuid4(),
        email="actor_new@test.com",
        is_deleted=False,
        hashed_password="",
    )
    db_session.add(user)
    await db_session.flush()

    actor = WorkspaceUser(
        workspace_id=str(workspace.id),
        user_id=str(user.id),
        role=WorkspaceRoleEnum.FULL_ADMIN,
        status="active",
        is_deleted=False,
    )
    db_session.add(actor)
    await db_session.flush()
    data = WorkspaceUserInviteRequest(email="stranger@test.com", role=WorkspaceRoleEnum.EDIT_ONLY)

    response = await service.invite_workspace_user(
        data=data,
        actor=actor,
    )

    assert response.email == "stranger@test.com"
    assert response.role == WorkspaceRoleEnum.EDIT_ONLY
    assert response.status == "pending"

    created_user = (await db_session.execute(select(User).where(User.email == "stranger@test.com"))).scalar_one()
    assert created_user.hashed_password == ""

    ws_user_res = (
        await db_session.execute(
            select(WorkspaceUser).where(
                WorkspaceUser.workspace_id == str(workspace.id),
                WorkspaceUser.user_id == created_user.id,
            )
        )
    ).scalar_one()
    assert ws_user_res is not None


async def test_invite_workspace_user_happy_path_existing_user_without_link(db_session):
    """Should leverage existing user profile but create a new pending link."""
    service = WorkspaceUserService(db_session)
    workspace = Workspace(name="WS", email="w3@t.com")
    db_session.add(workspace)
    await db_session.flush()

    user = User(
        id=uuid.uuid4(),
        email="actor_ex@test.com",
        is_deleted=False,
        hashed_password="",
    )
    existing_user = User(
        id=uuid.uuid4(),
        email="known@test.com",
        first_name="Known",
        last_name="User",
        is_deleted=False,
        hashed_password="pw",
    )
    db_session.add_all([user, existing_user])
    await db_session.flush()

    actor = WorkspaceUser(
        workspace_id=str(workspace.id),
        user_id=str(user.id),
        role=WorkspaceRoleEnum.FULL_ADMIN,
        status="active",
        is_deleted=False,
    )
    db_session.add(actor)
    await db_session.flush()
    data = WorkspaceUserInviteRequest(email="known@test.com", role=WorkspaceRoleEnum.READ_ONLY)

    response = await service.invite_workspace_user(data=data, actor=actor)
    assert response.id == existing_user.id
    assert response.name is None
    assert response.email == "known@test.com"
    assert response.role == WorkspaceRoleEnum.READ_ONLY


async def test_invite_workspace_user_exception_privilege_escalation(db_session):
    """Should block invitation if role is higher than actor's clearance."""
    service = WorkspaceUserService(db_session)
    workspace = Workspace(name="WS", email="w4@t.com")
    db_session.add(workspace)
    await db_session.flush()

    user = User(
        id=uuid.uuid4(),
        email="actor_esc@test.com",
        is_deleted=False,
        hashed_password="",
    )
    db_session.add(user)
    await db_session.flush()

    actor = WorkspaceUser(
        workspace_id=str(workspace.id),
        user_id=str(user.id),
        role=WorkspaceRoleEnum.EDIT_ONLY,
        status="active",
        is_deleted=False,
    )
    db_session.add(actor)
    await db_session.flush()
    data = WorkspaceUserInviteRequest(email="target@test.com", role=WorkspaceRoleEnum.FULL_ADMIN)

    with pytest.raises(PrivilegeEscalationBlockedError):
        await service.invite_workspace_user(data=data, actor=actor)


async def test_invite_workspace_user_exception_user_already_active(db_session):
    """Should raise WorkspaceUserAlreadyInWorkspaceError if target link is active."""
    service = WorkspaceUserService(db_session)
    workspace = Workspace(name="WS", email="w5@t.com")
    db_session.add(workspace)
    await db_session.flush()

    user = User(
        id=uuid.uuid4(),
        email="actor_active@test.com",
        is_deleted=False,
        hashed_password="",
    )
    target_user = User(
        id=uuid.uuid4(),
        email="active-member@test.com",
        is_deleted=False,
        hashed_password="",
    )
    db_session.add_all([user, target_user])
    await db_session.flush()

    actor = WorkspaceUser(
        workspace_id=str(workspace.id),
        user_id=str(user.id),
        role=WorkspaceRoleEnum.FULL_ADMIN,
        status="active",
        is_deleted=False,
    )
    target_link = WorkspaceUser(
        workspace_id=str(workspace.id),
        user_id=str(target_user.id),
        role="read_only",
        status="active",
        is_deleted=False,
    )

    db_session.add_all([actor, target_link])
    await db_session.flush()
    data = WorkspaceUserInviteRequest(email="active-member@test.com", role=WorkspaceRoleEnum.READ_ONLY)

    with pytest.raises(WorkspaceUserAlreadyInWorkspaceError):
        await service.invite_workspace_user(data=data, actor=actor)


async def test_invite_workspace_user_resurrects_soft_deleted_workspace_user(db_session):
    """Should restore and reset tracking metrics for soft-deleted workspace_users."""
    service = WorkspaceUserService(db_session)
    workspace = Workspace(name="WS", email="w6@t.com")
    db_session.add(workspace)
    await db_session.flush()

    user = User(
        id=uuid.uuid4(),
        email="actor_res@test.com",
        is_deleted=False,
        hashed_password="",
    )
    target_user = User(
        id=uuid.uuid4(),
        email="comeback@test.com",
        is_deleted=False,
        hashed_password="",
    )
    db_session.add_all([user, target_user])
    await db_session.flush()

    actor = WorkspaceUser(
        workspace_id=str(workspace.id),
        user_id=str(user.id),
        role=WorkspaceRoleEnum.FULL_ADMIN,
        status="active",
        is_deleted=False,
    )
    target_link = WorkspaceUser(
        workspace_id=str(workspace.id),
        user_id=str(target_user.id),
        role="read_only",
        status="active",
        is_deleted=True,
    )

    db_session.add_all([actor, target_link])
    await db_session.flush()
    data = WorkspaceUserInviteRequest(email="comeback@test.com", role=WorkspaceRoleEnum.EDIT_ONLY)

    response = await service.invite_workspace_user(data=data, actor=actor)

    assert response.status == "active"
    assert response.role == WorkspaceRoleEnum.EDIT_ONLY

    await db_session.refresh(target_link)
    assert target_link.is_deleted is False
    assert target_link.role == WorkspaceRoleEnum.EDIT_ONLY
    assert target_link.status == "active"


# ============================================================================
# ROLE UPDATE SERVICE TESTS (`update_workspace_user`)
# ============================================================================


async def test_update_workspace_user_happy_path(db_session):
    """Should modify member's role tier when hierarchy allows."""
    service = WorkspaceUserService(db_session)
    workspace = Workspace(name="WS", email="w7@t.com")
    db_session.add(workspace)
    await db_session.flush()

    actor_user = User(
        id=uuid.uuid4(),
        email="act_upd@test.com",
        is_deleted=False,
        hashed_password="",
    )
    target_user = User(
        id=uuid.uuid4(),
        email="tar_upd@test.com",
        is_deleted=False,
        hashed_password="",
    )
    db_session.add_all([actor_user, target_user])
    await db_session.flush()

    actor = WorkspaceUser(
        workspace_id=str(workspace.id),
        user_id=str(actor_user.id),
        role=WorkspaceRoleEnum.FULL_ADMIN,
        status="active",
        is_deleted=False,
    )
    target = WorkspaceUser(
        workspace_id=str(workspace.id),
        user_id=str(target_user.id),
        role="read_only",
        status="active",
        is_deleted=False,
    )
    db_session.add_all([actor, target])
    await db_session.flush()

    update_data = WorkspaceUserUpdateRequest(role=WorkspaceRoleEnum.EDIT_ONLY)
    await service.update_workspace_user(data=update_data, target_id=target.id, actor=actor)

    await db_session.refresh(target)
    assert target.role == WorkspaceRoleEnum.EDIT_ONLY


async def test_update_workspace_user_exception_self_modification_blocked(db_session):
    """Should instantly block users attempting to adjust their own roles."""
    service = WorkspaceUserService(db_session)

    # Persist parent models if foreign key constraints are enforced
    workspace = Workspace(name="WS", email="ws@test.com")
    user = User(id=uuid.uuid4(), email="actor@test.com", hashed_password="", is_deleted=False)
    db_session.add_all([workspace, user])
    await db_session.flush()

    actor = WorkspaceUser(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        user_id=user.id,
        role=WorkspaceRoleEnum.EDIT_ONLY,
    )
    db_session.add(actor)
    await db_session.flush()

    update_data = WorkspaceUserUpdateRequest(role=WorkspaceRoleEnum.FULL_ADMIN)

    with pytest.raises(SelfModificationBlockedError):
        await service.update_workspace_user(data=update_data, target_id=actor.id, actor=actor)


async def test_update_workspace_user_exception_rank_immunity_violation(db_session):
    """Should block users attempting to mutate roles of equal/higher tiers."""
    service = WorkspaceUserService(db_session)
    workspace = Workspace(name="WS", email="w8@t.com")
    db_session.add(workspace)
    await db_session.flush()

    actor_user = User(
        id=uuid.uuid4(),
        email="act_imm@test.com",
        is_deleted=False,
        hashed_password="",
    )
    target_user = User(
        id=uuid.uuid4(),
        email="tar_imm@test.com",
        is_deleted=False,
        hashed_password="",
    )
    db_session.add_all([actor_user, target_user])
    await db_session.flush()

    actor = WorkspaceUser(
        workspace_id=str(workspace.id),
        user_id=str(actor_user.id),
        role=WorkspaceRoleEnum.EDIT_ONLY,
        status="active",
        is_deleted=False,
    )
    target = WorkspaceUser(
        workspace_id=str(workspace.id),
        user_id=str(target_user.id),
        role=WorkspaceRoleEnum.FULL_ADMIN,
        status="active",
        is_deleted=False,
    )
    db_session.add_all([actor, target])
    await db_session.flush()

    update_data = WorkspaceUserUpdateRequest(role="read_only")

    with pytest.raises(RankImmunityViolationError):
        await service.update_workspace_user(data=update_data, target_id=target.id, actor=actor)


async def test_update_workspace_user_exception_privilege_escalation_blocked(db_session):
    """Should prevent user from raising a peer's role above their own."""
    service = WorkspaceUserService(db_session)
    workspace = Workspace(name="WS", email="w9@t.com")
    db_session.add(workspace)
    await db_session.flush()

    actor_user = User(
        id=uuid.uuid4(),
        email="act_esc_b@test.com",
        is_deleted=False,
        hashed_password="",
    )
    target_user = User(
        id=uuid.uuid4(),
        email="tar_esc_b@test.com",
        is_deleted=False,
        hashed_password="",
    )
    db_session.add_all([actor_user, target_user])
    await db_session.flush()

    actor = WorkspaceUser(
        workspace_id=str(workspace.id),
        user_id=str(actor_user.id),
        role=WorkspaceRoleEnum.EDIT_ONLY,
        status="active",
        is_deleted=False,
    )
    target = WorkspaceUser(
        workspace_id=str(workspace.id),
        user_id=str(target_user.id),
        role="read_only",
        status="active",
        is_deleted=False,
    )
    db_session.add_all([actor, target])
    await db_session.flush()

    update_data = WorkspaceUserUpdateRequest(role=WorkspaceRoleEnum.FULL_ADMIN)

    with pytest.raises(PrivilegeEscalationBlockedError):
        await service.update_workspace_user(data=update_data, target_id=target.id, actor=actor)


# ============================================================================
# MEMBER REMOVAL SERVICE TESTS (`update_workspace_user`)
# ============================================================================


async def test_remove_member_happy_path(db_session):
    """Should soft-delete relationship record when hierarchy allows."""
    service = WorkspaceUserService(db_session)
    workspace = Workspace(name="WS", email="w10@t.com")
    db_session.add(workspace)
    await db_session.flush()

    actor_user = User(
        id=uuid.uuid4(),
        email="act_rem@test.com",
        is_deleted=False,
        hashed_password="",
    )
    target_user = User(
        id=uuid.uuid4(),
        email="tar_rem@test.com",
        is_deleted=False,
        hashed_password="",
    )
    db_session.add_all([actor_user, target_user])
    await db_session.flush()

    actor = WorkspaceUser(
        workspace_id=str(workspace.id),
        user_id=str(actor_user.id),
        role=WorkspaceRoleEnum.FULL_ADMIN,
        status="active",
        is_deleted=False,
    )
    target = WorkspaceUser(
        workspace_id=str(workspace.id),
        user_id=str(target_user.id),
        role="read_only",
        status="active",
        is_deleted=False,
    )
    db_session.add_all([actor, target])
    await db_session.flush()

    update_data = WorkspaceUserUpdateRequest(status="revoked", is_deleted=True)
    await service.update_workspace_user(data=update_data, target_id=target.id, actor=actor)

    await db_session.refresh(target)
    assert target.is_deleted is True


async def test_remove_member_exception_self_eviction_blocked(db_session):
    """Should explicitly prevent users from deleting their own membership when changing role."""
    service = WorkspaceUserService(db_session)

    workspace = Workspace(name="WS", email="ws1@t.com")
    user = User(
        id=uuid.uuid4(),
        email="act_rem_i@test.com",
        is_deleted=False,
        hashed_password="",
    )
    db_session.add_all([workspace, user])
    await db_session.flush()

    actor = WorkspaceUser(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        user_id=user.id,
        role=WorkspaceRoleEnum.FULL_ADMIN,
    )
    db_session.add(actor)
    await db_session.flush()

    update_data = WorkspaceUserUpdateRequest(is_deleted=True, role=WorkspaceRoleEnum.FULL_ADMIN)

    with pytest.raises(SelfEvictionBlockedError):
        await service.update_workspace_user(data=update_data, target_id=actor.id, actor=actor)


async def test_remove_member_exception_rank_immunity_violation(db_session):
    """Should protect higher or equal tier accounts from deletion."""
    service = WorkspaceUserService(db_session)
    workspace = Workspace(name="WS", email="ws1@t.com")
    db_session.add(workspace)
    await db_session.flush()

    actor_user = User(
        id=uuid.uuid4(),
        email="act_rem_i@test.com",
        is_deleted=False,
        hashed_password="",
    )
    target_user = User(
        id=uuid.uuid4(),
        email="tar_rem_i@test.com",
        is_deleted=False,
        hashed_password="",
    )
    db_session.add_all([actor_user, target_user])
    await db_session.flush()

    actor = WorkspaceUser(
        workspace_id=str(workspace.id),
        user_id=str(actor_user.id),
        role=WorkspaceRoleEnum.EDIT_ONLY,
        status="active",
        is_deleted=False,
    )
    target = WorkspaceUser(
        workspace_id=str(workspace.id),
        user_id=str(target_user.id),
        role=WorkspaceRoleEnum.FULL_ADMIN,
        status="active",
        is_deleted=False,
    )
    db_session.add_all([actor, target])
    await db_session.flush()

    update_data = WorkspaceUserUpdateRequest(is_deleted=True)

    with pytest.raises(RankImmunityViolationError):
        await service.update_workspace_user(data=update_data, target_id=target.id, actor=actor)


# ============================================================================
# BASE USER UPDATE SERVICE TESTS (`update_user`)
# ============================================================================


async def test_update_user_happy_path(db_session):
    """Verifies that base user profile attributes are correctly updated and persisted."""
    service = WorkspaceUserService(db_session)

    user = User(
        id=uuid.uuid4(),
        email="update_profile@test.com",
        first_name="OldFirst",
        last_name="OldLast",
        is_deleted=False,
        hashed_password="",
    )
    db_session.add(user)
    await db_session.flush()

    update_data = UserUpdateRequest(first_name="NewFirst", last_name="NewLast")

    updated_user = await service.update_user(user, update_data)

    # Check returned entity
    assert updated_user.first_name == "NewFirst"
    assert updated_user.last_name == "NewLast"

    # Check DB persistence
    await db_session.refresh(user)
    assert user.first_name == "NewFirst"
    assert user.last_name == "NewLast"
