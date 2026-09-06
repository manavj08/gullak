"""
Permission helpers for the splits app.

Membership-gated access follows the same "member-only, 404 for non-members"
convention used elsewhere in this project (e.g. expenses/social apps) --
hiding whether a group exists at all from non-members, rather than
returning 403 and leaking that information.
"""
from .services import is_member


def user_is_group_member(group, user):
    return is_member(group, user.id)


def user_can_manage_expense(expense, user):
    """Only the person who logged an expense or the payer may delete it."""
    return user.id in (expense.created_by_id, expense.paid_by_id)


def user_can_remove_member(group, target_user_id, requesting_user):
    """The creator may remove anyone; any member may remove only themselves."""
    return requesting_user.id == target_user_id or requesting_user.id == group.created_by_id


def user_can_mark_settlement_paid(settlement, user):
    """Only the payee (the person who was owed money) may confirm payment."""
    return user.id == settlement.payee_id
