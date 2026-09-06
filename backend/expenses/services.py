"""
Business logic for expense splitting and settlement generation, kept out of
views.py per the project's existing convention (see social/services.py).
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction as db_transaction

from social.models import SharedAccountMember, Notification, NotificationType
from .models import ExpenseEntry, ExpenseShare, ExpenseSplitType, Settlement, SettlementStatus

ZERO = Decimal('0.00')
CENT = Decimal('0.01')


def _member_ids(account):
    return set(SharedAccountMember.objects.filter(account=account).values_list('user_id', flat=True))


@db_transaction.atomic
def log_expense(*, account, created_by, paid_by_id, description, amount, category,
                 split_type, expense_date, note, participant_ids, exact_shares=None):
    """
    Create an ExpenseEntry + its ExpenseShare rows.

    - participant_ids: user ids sharing the expense (must all be current members).
    - exact_shares: required when split_type == EXACT; dict {user_id: Decimal amount},
      must sum exactly to `amount`.
    """
    members = _member_ids(account)
    if paid_by_id not in members:
        raise ValidationError({'paid_by': 'Payer must be a current member of this group.'})
    if created_by.id not in members:
        raise ValidationError({'created_by': 'Only group members can log expenses.'})
    if not participant_ids:
        raise ValidationError({'participants': 'Select at least one participant.'})
    if not set(participant_ids).issubset(members):
        raise ValidationError({'participants': 'All participants must be current members of this group.'})

    entry = ExpenseEntry.objects.create(
        account=account, paid_by_id=paid_by_id, created_by=created_by, description=description,
        amount=amount, category=category, split_type=split_type, expense_date=expense_date, note=note,
    )

    if split_type == ExpenseSplitType.EQUAL:
        shares = _equal_shares(amount, participant_ids)
    else:
        if not exact_shares:
            entry.delete()
            raise ValidationError({'exact_shares': 'Exact amounts are required for an exact split.'})
        shares = {int(uid): Decimal(str(v)) for uid, v in exact_shares.items()}
        if set(shares.keys()) != set(participant_ids):
            entry.delete()
            raise ValidationError({'exact_shares': 'Exact amounts must be provided for exactly the selected participants.'})
        total = sum(shares.values())
        if total != amount:
            entry.delete()
            raise ValidationError({'exact_shares': f'Exact amounts must add up to the total (₹{amount}), got ₹{total}.'})
        if any(v < 0 for v in shares.values()):
            entry.delete()
            raise ValidationError({'exact_shares': 'Shares cannot be negative.'})

    ExpenseShare.objects.bulk_create([
        ExpenseShare(expense=entry, user_id=uid, share_amount=amt) for uid, amt in shares.items()
    ])
    return entry


def _equal_shares(amount: Decimal, participant_ids: list[int]) -> dict[int, Decimal]:
    """Split `amount` equally across participants, distributing the rounding remainder
    (from paise-level division) across the first few participants (stable order) so the
    shares always sum exactly to `amount`."""
    n = len(participant_ids)
    base = (amount / n).quantize(CENT, rounding='ROUND_DOWN')
    remainder = amount - (base * n)
    remainder_cents = int((remainder / CENT).to_integral_value())

    ordered = sorted(participant_ids)
    shares = {}
    for i, uid in enumerate(ordered):
        extra = CENT if i < remainder_cents else ZERO
        shares[uid] = base + extra
    return shares


def delete_expense(*, expense, requesting_user):
    """Only the person who logged it or the payer may delete it."""
    if requesting_user.id not in (expense.created_by_id, expense.paid_by_id):
        raise ValidationError({'detail': 'Only the payer or the person who logged this expense can delete it.'})
    expense.delete()


@db_transaction.atomic
def generate_settlements(*, account):
    """
    Recompute net balances from all ExpenseShare rows tied to this account's
    unsettled expenses, then produce a minimal set of payer->payee transfers
    using a greedy max-debtor/max-creditor matching (standard debt-simplification
    heuristic — minimizes transaction count, not necessarily "fair" pairing by
    who-owed-whom-directly).

    Existing PENDING settlements for the account are replaced; PAID settlements
    are left untouched as history and their already-settled amounts are excluded
    from the recomputed net balances (see _net_balances).
    """
    net = _net_balances(account)

    # Drop near-zero balances (paisa rounding).
    net = {uid: bal for uid, bal in net.items() if abs(bal) >= CENT}

    debtors = sorted([(uid, -bal) for uid, bal in net.items() if bal < 0], key=lambda x: -x[1])  # owes money
    creditors = sorted([(uid, bal) for uid, bal in net.items() if bal > 0], key=lambda x: -x[1])  # is owed money

    Settlement.objects.filter(account=account, status=SettlementStatus.PENDING).delete()

    results = []
    i, j = 0, 0
    debtors = [list(d) for d in debtors]
    creditors = [list(c) for c in creditors]
    while i < len(debtors) and j < len(creditors):
        debtor_id, owes = debtors[i]
        creditor_id, owed = creditors[j]
        settle_amount = min(owes, owed)
        if settle_amount >= CENT:
            s = Settlement.objects.create(
                account=account, payer_id=debtor_id, payee_id=creditor_id,
                amount=settle_amount.quantize(CENT),
            )
            results.append(s)
        debtors[i][1] -= settle_amount
        creditors[j][1] -= settle_amount
        if debtors[i][1] < CENT:
            i += 1
        if creditors[j][1] < CENT:
            j += 1

    return results


def _net_balances(account) -> dict[int, Decimal]:
    """
    Positive balance = is owed money overall; negative = owes money overall.

    Step 1 — raw balance from every logged expense: the payer is credited the
    full amount, every participant (including the payer, if they're also a
    participant) is debited their share.

    Step 2 — offset by every settlement already marked PAID: a paid settlement
    is a real payer->payee transfer, so it reduces the payer's debt and the
    payee's credit by the same amount. This keeps regenerated settlements from
    re-asking for money that has already been confirmed paid.
    """
    balances: dict[int, Decimal] = {}

    def add(uid, delta):
        balances[uid] = balances.get(uid, ZERO) + delta

    entries = ExpenseEntry.objects.filter(account=account).prefetch_related('shares')
    for entry in entries:
        add(entry.paid_by_id, entry.amount)
        for share in entry.shares.all():
            add(share.user_id, -share.share_amount)

    for s in Settlement.objects.filter(account=account, status=SettlementStatus.PAID):
        add(s.payer_id, s.amount)
        add(s.payee_id, -s.amount)

    return balances


def mark_settlement_paid(*, settlement, requesting_user):
    """Only the payee (who received the money) can confirm it was paid."""
    if requesting_user.id != settlement.payee_id:
        raise ValidationError({'detail': 'Only the person who was owed money can mark a settlement as paid.'})
    if settlement.status == SettlementStatus.PAID:
        return settlement
    from django.utils import timezone
    settlement.status = SettlementStatus.PAID
    settlement.paid_at = timezone.now()
    settlement.marked_paid_by = requesting_user
    settlement.save(update_fields=['status', 'paid_at', 'marked_paid_by'])

    Notification.objects.create(
        user=settlement.payer, type=NotificationType.SETTLEMENT_PAID,
        title='Settlement confirmed paid',
        body=f'{settlement.payee.username} confirmed your ₹{settlement.amount} payment for {settlement.account.name}.',
        related_entity_id=settlement.id,
    )
    return settlement
