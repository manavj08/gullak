"""Expense creation/deletion for the splits app. All share-amount math is
delegated to services.settlement (the single source of truth for rounding
rules) — this module only handles validation and persistence."""
from django.core.exceptions import ValidationError
from django.db import transaction as db_transaction

from ..models import SplitExpense, SplitExpenseShare, SplitType
from . import settlement as settlement_service
from .groups import member_ids


@db_transaction.atomic
def create_expense(*, group, created_by, paid_by_id, description, amount, split_type,
                    expense_date, note='', participant_ids=None, exact_shares=None, percentages=None):
    members = member_ids(group)
    if created_by.id not in members:
        raise ValidationError({'detail': 'Only group members can add expenses.'})
    if paid_by_id not in members:
        raise ValidationError({'paid_by': 'Payer must be a current member of this group.'})
    participant_ids = list(participant_ids or [])
    if not participant_ids:
        raise ValidationError({'participant_ids': 'Select at least one participant.'})
    if not set(participant_ids).issubset(members):
        raise ValidationError({'participant_ids': 'All participants must be current members of this group.'})

    expense = SplitExpense.objects.create(
        group=group, description=description, amount=amount, paid_by_id=paid_by_id,
        created_by=created_by, split_type=split_type, expense_date=expense_date, note=note,
    )

    try:
        if split_type == SplitType.EQUAL:
            shares, percentages_by_uid = settlement_service.equal_shares(amount, participant_ids), {}
        elif split_type == SplitType.CUSTOM:
            shares, percentages_by_uid = settlement_service.custom_shares(amount, participant_ids, exact_shares), {}
        elif split_type == SplitType.PERCENTAGE:
            shares, percentages_by_uid = settlement_service.percentage_shares(amount, participant_ids, percentages)
        else:
            raise ValidationError({'split_type': 'Unknown split type.'})
    except ValidationError:
        expense.delete()
        raise

    SplitExpenseShare.objects.bulk_create([
        SplitExpenseShare(expense=expense, user_id=uid, share_amount=amt, percentage=percentages_by_uid.get(uid))
        for uid, amt in shares.items()
    ])
    return expense


def delete_expense(*, expense, requesting_user):
    if requesting_user.id not in (expense.created_by_id, expense.paid_by_id):
        raise ValidationError({'detail': 'Only the payer or the person who logged this expense can delete it.'})
    expense.delete()
