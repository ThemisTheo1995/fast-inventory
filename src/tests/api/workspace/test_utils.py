import pytest

from erp.api.workspace.exceptions import (
    PrivilegeEscalationBlocked,
    RankImmunityViolation,
    SelfEvictionBlocked,
    SelfModificationBlocked,
)
from erp.api.workspace.utils import (
    guard_against_self_action,
    guard_privilege_escalation,
    guard_rank_immunity,
)

# ============================================================================
# SELF ACTION GUARD TESTS (`guard_against_self_action`)
# ============================================================================


def test_guard_against_self_action_happy_path():
    """
    When the actor ID and target user ID are different, the function should 
    execute cleanly and return None (no exceptions raised).
    """
    # Checking both modification and eviction permutations
    assert guard_against_self_action(actor_id="user_123", target_user_id="user_999", is_eviction=False) is None
    assert guard_against_self_action(actor_id="user_123", target_user_id="user_999", is_eviction=True) is None


def test_guard_against_self_action_raises_self_modification():
    """
    When an actor tries to modify themselves (actor_id == target_user_id) 
    and is_eviction is False, it must raise SelfModificationBlocked.
    """
    with pytest.raises(SelfModificationBlocked):
        guard_against_self_action(actor_id="user_123", target_user_id="user_123", is_eviction=False)


def test_guard_against_self_action_raises_self_eviction():
    """
    When an actor tries to evict themselves (actor_id == target_user_id) 
    and is_eviction is True, it must raise SelfEvictionBlocked.
    """
    with pytest.raises(SelfEvictionBlocked):
        guard_against_self_action(actor_id="user_123", target_user_id="user_123", is_eviction=True)


# ============================================================================
# RANK IMMUNITY GUARD TESTS (`guard_rank_immunity`)
# ============================================================================

@pytest.mark.parametrize("actor_role, target_member_role", [
    ("full_admin", "edit_only"),  # Higher rank acting on lower rank
    ("full_admin", "read_only"),  # Higher rank acting on lowest rank
    ("edit_only", "read_only"),   # Mid rank acting on lowest rank
    ("full_admin", "full_admin"), # Equal tier: Admin acting on Admin
    ("edit_only", "edit_only"),   # Equal tier: Editor acting on Editor
    ("read_only", "read_only"),   # Equal tier: Reader acting on Reader
])
def test_guard_rank_immunity_happy_paths(actor_role, target_member_role):
    """
    Actors with a higher or equal tier weight can safely manage target users 
    without triggering immunity blocks.
    """
    assert guard_rank_immunity(actor_role, target_member_role) is None


@pytest.mark.parametrize("actor_role, target_member_role", [
    ("edit_only", "full_admin"),  # Lower rank trying to modify higher rank
    ("read_only", "full_admin"),  # Lowest rank trying to modify highest rank
    ("read_only", "edit_only"),   # Lowest rank trying to modify mid rank
])
def test_guard_rank_immunity_raises_violation(actor_role, target_member_role):
    """
    When an actor has a strictly lower weight than their target, the function 
    must defend the higher-tier user and raise RankImmunityViolation.
    """
    with pytest.raises(RankImmunityViolation):
        guard_rank_immunity(actor_role, target_member_role)


@pytest.mark.parametrize("actor_role, target_member_role", [
    ("FULL_ADMIN", "edit_only"),   # Uppercase actor string
    ("edit_only", "READ_ONLY"),    # Uppercase target string
    ("EdIt_OnLy", "FuLl_AdMiN"),   # Mixed-case string triggering exception path
])
def test_guard_rank_immunity_edge_cases_case_insensitivity(actor_role, target_member_role):
    """
    The guard handles case-insensitivity seamlessly due to internal string normalization.
    """
    if actor_role.lower() == "full_admin" or target_member_role.lower() == "read_only":
        assert guard_rank_immunity(actor_role, target_member_role) is None

    # Mixed case that should be caught and rejected correctly
    if actor_role.lower() == "edit_only" and target_member_role.lower() == "full_admin":
        with pytest.raises(RankImmunityViolation):
            guard_rank_immunity(actor_role, target_member_role)


@pytest.mark.parametrize("actor_role, target_member_role, should_raise", [
    ("unregistered_guest_role", "read_only", False),       # 1 vs 1 (Equal weight fallback -> passes)
    ("unregistered_guest_role", "full_admin", True),       # 1 vs 3 (Lower fallback -> raises)
    ("full_admin", "some_corrupted_role_string", False),  # 3 vs 1 (Higher fallback -> passes)
])
def test_guard_rank_immunity_edge_cases_unknown_roles(actor_role, target_member_role, should_raise):
    """
    If a role is passed that doesn't exist in ROLE_WEIGHTS, it should safely fall back
    to a default weight value of 1 without throwing a KeyError.
    """
    if should_raise:
        with pytest.raises(RankImmunityViolation):
            guard_rank_immunity(actor_role, target_member_role)
    else:
        assert guard_rank_immunity(actor_role, target_member_role) is None


# ============================================================================
# PRIVILEGE ESCALATION GUARD TESTS (`guard_privilege_escalation`)
# ============================================================================

@pytest.mark.parametrize("actor_role, requested_role", [
    ("full_admin", "full_admin"),   # Assigning an equal top tier
    ("full_admin", "edit_only"),    # Assigning a lower tier
    ("edit_only", "edit_only"),     # Assigning an equal mid tier
    ("edit_only", "read_only"),     # Assigning a lower tier
    ("read_only", "read_only"),     # Assigning an equal low tier
])
def test_guard_privilege_escalation_happy_paths(actor_role, requested_role):
    """
    An actor can always assign or invite a user to a role that is less than
    or completely equal to their own weight tier.
    """
    assert guard_privilege_escalation(actor_role, requested_role) is None


@pytest.mark.parametrize("actor_role, requested_role", [
    ("edit_only", "full_admin"),  # Editor trying to grant Admin powers
    ("read_only", "full_admin"),  # Reader trying to grant Admin powers
    ("read_only", "edit_only"),   # Reader trying to grant Editor powers
])
def test_guard_privilege_escalation_raises_violation(actor_role, requested_role):
    """
    EXCEPTION PATH:
    An actor attempting to grant a role carrying a strictly heavier weight than
    their own must be blocked by a PrivilegeEscalationBlocked exception.
    """
    with pytest.raises(PrivilegeEscalationBlocked):
        guard_privilege_escalation(actor_role, requested_role)


def test_guard_privilege_escalation_edge_cases_unknown_and_case():
    """
    EDGE CASES:
    Verifies string normalization handling (.lower()) and fallback tracking (defaulting to 1)
    for unknown inputs during role assignment attempts.
    """
    # Case insensitivity happy check
    assert guard_privilege_escalation("EDIT_ONLY", "read_only") is None

    # Unknown actor role fallback (defaults to 1) trying to grant a level 2 role (Blocked)
    with pytest.raises(PrivilegeEscalationBlocked):
        guard_privilege_escalation("anonymous_ghost_role", "edit_only")

    # Unknown requested role fallback (defaults to 1) being assigned by an Editor (Allowed)
    assert guard_privilege_escalation("edit_only", "strange_new_permission_tier") is None
