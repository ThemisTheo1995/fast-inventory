import uuid

import pytest

from erp.api.auth.models import User
from erp.api.workspace.exceptions import (
    PrivilegeEscalationBlockedError,
    RankImmunityViolationError,
    SelfEvictionBlockedError,
    SelfModificationBlockedError,
    UserAlreadyActiveMemberError,
    WorkspaceMemberNotFoundError,
)
from erp.api.workspace.models import Workspace, WorkspaceUser
from erp.api.workspace.schemas.workspace_user import WorkspaceUserResponse
from erp.api.workspace.service import WorkspaceUserService

# ============================================================================
# LOOKUP HELPER TESTS (`_get_active_workspace_user`)
# ============================================================================


def test_get_active_workspace_user_happy_path(db_session):
    """Should return the WorkspaceUser record when it exists."""
    service = WorkspaceUserService(db_session)

    workspace = Workspace(name="WS", email="w@t.com")
    db_session.add(workspace)
    db_session.flush()

    user = User(
        id=uuid.uuid4(),
        email="lookup_happy@test.com",
        is_deleted=False,
        hashed_password="",
    )
    db_session.add(user)
    db_session.flush()

    link = WorkspaceUser(
        workspace_id=str(workspace.id),
        user_id=str(user.id),
        role="edit_only",
        status="active",
        is_deleted=False,
    )
    db_session.add(link)
    db_session.flush()

    result = service._get_active_workspace_user(str(workspace.id), str(user.id))
    assert result.workspace_id == str(workspace.id)
    assert result.user_id == str(user.id)


def test_get_active_workspace_user_raises_not_found_if_missing(db_session):
    """Should raise WorkspaceMemberNotFoundError if no matching record exists."""
    service = WorkspaceUserService(db_session)
    with pytest.raises(WorkspaceMemberNotFoundError):
        service._get_active_workspace_user(str(uuid.uuid4()), str(uuid.uuid4()))


def test_get_active_workspace_user_raises_not_found_if_soft_deleted(db_session):
    """Should treat soft-deleted workspace members as non-existent."""
    service = WorkspaceUserService(db_session)

    workspace = Workspace(name="WS", email="w01@t.com")
    db_session.add(workspace)
    db_session.flush()

    user = User(
        id=uuid.uuid4(),
        email="lookup_soft@test.com",
        is_deleted=False,
        hashed_password="",
    )
    db_session.add(user)
    db_session.flush()

    link = WorkspaceUser(
        workspace_id=str(workspace.id),
        user_id=str(user.id),
        role="edit_only",
        status="active",
        is_deleted=True,
    )
    db_session.add(link)
    db_session.flush()

    with pytest.raises(WorkspaceMemberNotFoundError):
        service._get_active_workspace_user(str(workspace.id), str(user.id))


# ============================================================================
# FETCH MEMBERS TESTS (`get_workspace_users`)
# ============================================================================


def test_get_workspace_users_happy_path_and_name_formatting(db_session):
    """Should fetch all active members and format full names correctly."""
    service = WorkspaceUserService(db_session)
    workspace = Workspace(name="WS", email="w1@t.com")
    db_session.add(workspace)
    db_session.flush()

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
        role="full_admin",
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
    db_session.flush()

    members = service.get_workspace_users(str(workspace.id))

    assert len(members) == 2
    assert isinstance(members[0], WorkspaceUserResponse)
    assert members[0].id == u1.id
    assert members[0].name == "John Doe"
    assert members[1].name == "Solo"


def test_get_workspace_users_excludes_soft_deleted_records(db_session):
    """Should ignore workspace links or user records that are soft-deleted."""
    service = WorkspaceUserService(db_session)
    workspace = Workspace(name="WS", email="w2@t.com")
    db_session.add(workspace)
    db_session.flush()

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
    db_session.flush()

    members = service.get_workspace_users(str(workspace.id))
    assert len(members) == 1
    assert members[0].id == u_active.id


# ============================================================================
# INVITATION SERVICE TESTS (`invite_member`)
# ============================================================================


def test_invite_member_happy_path_new_user(db_session):
    """Should create a fresh User shell and link record on invitation."""
    service = WorkspaceUserService(db_session)
    workspace = Workspace(name="WS", email="w02@t.com")
    db_session.add(workspace)
    db_session.flush()

    actor = User(
        id=uuid.uuid4(),
        email="actor_new@test.com",
        is_deleted=False,
        hashed_password="",
    )
    db_session.add(actor)
    db_session.flush()

    actor_link = WorkspaceUser(
        workspace_id=str(workspace.id),
        user_id=str(actor.id),
        role="full_admin",
        status="active",
        is_deleted=False,
    )
    db_session.add(actor_link)
    db_session.flush()

    response = service.invite_member(
        str(workspace.id),
        email="stranger@test.com",
        role="edit_only",
        actor_id=str(actor.id),
    )

    assert response.email == "stranger@test.com"
    assert response.role_id == "edit_only"
    assert response.status == "pending"

    created_user = db_session.query(User).filter_by(email="stranger@test.com").one()
    assert created_user.hashed_password == ""
    assert db_session.query(WorkspaceUser).filter_by(workspace_id=str(workspace.id), user_id=created_user.id).one()


def test_invite_member_happy_path_existing_user_without_link(db_session):
    """Should leverage existing user profile but create a new pending link."""
    service = WorkspaceUserService(db_session)
    workspace = Workspace(name="WS", email="w3@t.com")
    db_session.add(workspace)
    db_session.flush()

    actor = User(
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
    db_session.add_all([actor, existing_user])
    db_session.flush()

    actor_link = WorkspaceUser(
        workspace_id=str(workspace.id),
        user_id=str(actor.id),
        role="full_admin",
        status="active",
        is_deleted=False,
    )
    db_session.add(actor_link)
    db_session.flush()

    response = service.invite_member(
        str(workspace.id),
        email="known@test.com",
        role="read_only",
        actor_id=str(actor.id),
    )
    assert response.id == existing_user.id
    assert response.name is None
    assert response.email == "known@test.com"


def test_invite_member_exception_privilege_escalation(db_session):
    """Should block invitation if role is higher than actor's clearance."""
    service = WorkspaceUserService(db_session)
    workspace = Workspace(name="WS", email="w4@t.com")
    db_session.add(workspace)
    db_session.flush()

    actor = User(
        id=uuid.uuid4(),
        email="actor_esc@test.com",
        is_deleted=False,
        hashed_password="",
    )
    db_session.add(actor)
    db_session.flush()

    actor_link = WorkspaceUser(
        workspace_id=str(workspace.id),
        user_id=str(actor.id),
        role="edit_only",
        status="active",
        is_deleted=False,
    )
    db_session.add(actor_link)
    db_session.flush()

    with pytest.raises(PrivilegeEscalationBlockedError):
        service.invite_member(
            str(workspace.id),
            email="target@test.com",
            role="full_admin",
            actor_id=str(actor.id),
        )


def test_invite_member_exception_user_already_active(db_session):
    """Should raise UserAlreadyActiveMemberError if target link is active."""
    service = WorkspaceUserService(db_session)
    workspace = Workspace(name="WS", email="w5@t.com")
    db_session.add(workspace)
    db_session.flush()

    actor = User(
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
    db_session.add_all([actor, target_user])
    db_session.flush()

    actor_link = WorkspaceUser(
        workspace_id=str(workspace.id),
        user_id=str(actor.id),
        role="full_admin",
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

    db_session.add_all([actor_link, target_link])
    db_session.flush()

    with pytest.raises(UserAlreadyActiveMemberError):
        service.invite_member(
            str(workspace.id),
            email="active-member@test.com",
            role="read_only",
            actor_id=str(actor.id),
        )


def test_invite_member_resurrects_soft_deleted_link(db_session):
    """Should restore and reset tracking metrics for soft-deleted links."""
    service = WorkspaceUserService(db_session)
    workspace = Workspace(name="WS", email="w6@t.com")
    db_session.add(workspace)
    db_session.flush()

    actor = User(
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
    db_session.add_all([actor, target_user])
    db_session.flush()

    actor_link = WorkspaceUser(
        workspace_id=str(workspace.id),
        user_id=str(actor.id),
        role="full_admin",
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

    db_session.add_all([actor_link, target_link])
    db_session.flush()

    response = service.invite_member(
        str(workspace.id),
        email="comeback@test.com",
        role="edit_only",
        actor_id=str(actor.id),
    )

    assert response.status == "pending"
    assert response.role_id == "edit_only"

    db_session.refresh(target_link)
    assert target_link.is_deleted is False
    assert target_link.role == "edit_only"
    assert target_link.status == "pending"


# ============================================================================
# ROLE UPDATE SERVICE TESTS (`update_role`)
# ============================================================================


def test_update_role_happy_path(db_session):
    """Should modify member's role tier when hierarchy allows."""
    service = WorkspaceUserService(db_session)
    workspace = Workspace(name="WS", email="w7@t.com")
    db_session.add(workspace)
    db_session.flush()

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
    db_session.flush()

    actor = WorkspaceUser(
        workspace_id=str(workspace.id),
        user_id=str(actor_user.id),
        role="full_admin",
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
    db_session.flush()

    service.update_role(
        str(workspace.id),
        target_user_id=str(target_user.id),
        new_role="edit_only",
        actor_id=str(actor_user.id),
    )

    db_session.refresh(target)
    assert target.role == "edit_only"


def test_update_role_exception_self_modification_blocked(db_session):
    """Should instantly block users attempting to adjust their own roles."""
    service = WorkspaceUserService(db_session)
    ws_id = str(uuid.uuid4())
    actor_id = str(uuid.uuid4())

    with pytest.raises(SelfModificationBlockedError):
        service.update_role(ws_id, target_user_id=actor_id, new_role="full_admin", actor_id=actor_id)


def test_update_role_exception_rank_immunity_violation(db_session):
    """Should block users attempting to mutate roles of equal/higher tiers."""
    service = WorkspaceUserService(db_session)
    workspace = Workspace(name="WS", email="w8@t.com")
    db_session.add(workspace)
    db_session.flush()

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
    db_session.flush()

    actor = WorkspaceUser(
        workspace_id=str(workspace.id),
        user_id=str(actor_user.id),
        role="edit_only",
        status="active",
        is_deleted=False,
    )
    target = WorkspaceUser(
        workspace_id=str(workspace.id),
        user_id=str(target_user.id),
        role="full_admin",
        status="active",
        is_deleted=False,
    )
    db_session.add_all([actor, target])
    db_session.flush()

    with pytest.raises(RankImmunityViolationError):
        service.update_role(
            str(workspace.id),
            target_user_id=str(target_user.id),
            new_role="read_only",
            actor_id=str(actor_user.id),
        )


def test_update_role_exception_privilege_escalation_blocked(db_session):
    """Should prevent user from raising a peer's role above their own."""
    service = WorkspaceUserService(db_session)
    workspace = Workspace(name="WS", email="w9@t.com")
    db_session.add(workspace)
    db_session.flush()

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
    db_session.flush()

    actor = WorkspaceUser(
        workspace_id=str(workspace.id),
        user_id=str(actor_user.id),
        role="edit_only",
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
    db_session.flush()

    with pytest.raises(PrivilegeEscalationBlockedError):
        service.update_role(
            str(workspace.id),
            target_user_id=str(target_user.id),
            new_role="full_admin",
            actor_id=str(actor_user.id),
        )


# ============================================================================
# MEMBER REMOVAL SERVICE TESTS (`remove_member`)
# ============================================================================


def test_remove_member_happy_path(db_session):
    """Should soft-delete relationship record when hierarchy allows."""
    service = WorkspaceUserService(db_session)
    workspace = Workspace(name="WS", email="w10@t.com")
    db_session.add(workspace)
    db_session.flush()

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
    db_session.flush()

    actor = WorkspaceUser(
        workspace_id=str(workspace.id),
        user_id=str(actor_user.id),
        role="full_admin",
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
    db_session.flush()

    service.remove_member(
        str(workspace.id),
        target_user_id=str(target_user.id),
        actor_id=str(actor_user.id),
    )

    db_session.refresh(target)
    assert target.is_deleted is True


def test_remove_member_exception_self_eviction_blocked(db_session):
    """Should explicitly prevent users from deleting their own membership."""
    service = WorkspaceUserService(db_session)
    ws_id = str(uuid.uuid4())
    actor_id = str(uuid.uuid4())

    with pytest.raises(SelfEvictionBlockedError):
        service.remove_member(ws_id, target_user_id=actor_id, actor_id=actor_id)


def test_remove_member_exception_rank_immunity_violation(db_session):
    """Should protect higher or equal tier accounts from deletion."""
    service = WorkspaceUserService(db_session)
    workspace = Workspace(name="WS", email="ws1@t.com")
    db_session.add(workspace)
    db_session.flush()

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
    db_session.flush()

    actor = WorkspaceUser(
        workspace_id=str(workspace.id),
        user_id=str(actor_user.id),
        role="edit_only",
        status="active",
        is_deleted=False,
    )
    target = WorkspaceUser(
        workspace_id=str(workspace.id),
        user_id=str(target_user.id),
        role="full_admin",
        status="active",
        is_deleted=False,
    )
    db_session.add_all([actor, target])
    db_session.flush()

    with pytest.raises(RankImmunityViolationError):
        service.remove_member(
            str(workspace.id),
            target_user_id=str(target_user.id),
            actor_id=str(actor_user.id),
        )
