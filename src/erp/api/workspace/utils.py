from erp.api.workspace.exceptions import (
    PrivilegeEscalationBlockedError,
    RankImmunityViolationError,
    SelfEvictionBlockedError,
    SelfModificationBlockedError,
)

ROLE_WEIGHTS = {
    "full_admin": 3,
    "edit_only": 2,
    "read_only": 1
}


def guard_against_self_action(actor_id: str, target_user_id: str, is_eviction: bool = False) -> None:
    """RULE 1: Prevent users from managing or deleting their own roles."""
    if actor_id == target_user_id:
        raise SelfEvictionBlockedError() if is_eviction else SelfModificationBlockedError()


def guard_rank_immunity(actor_role: str, target_member_role: str) -> None:
    """RULE 2: Lower-tier roles cannot modify or delete higher roles."""
    actor_weight = ROLE_WEIGHTS.get(actor_role.lower(), 1)
    target_weight = ROLE_WEIGHTS.get(target_member_role.lower(), 1)

    if target_weight > actor_weight:
        raise RankImmunityViolationError()


def guard_privilege_escalation(actor_role: str, requested_role: str) -> None:
    """RULE 3: You cannot assign or invite someone to a role higher than your own."""
    actor_weight = ROLE_WEIGHTS.get(actor_role.lower(), 1)
    requested_weight = ROLE_WEIGHTS.get(requested_role.lower(), 1)

    if requested_weight > actor_weight:
        raise PrivilegeEscalationBlockedError()
