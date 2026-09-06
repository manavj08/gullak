"""
Settlement mathematics for the splits app — split-type share calculation,
pairwise debt netting, global debt simplification, and the "show
calculation" explainability trail.

This module is the single source of truth for every money computation in
`splits`. Everything here uses Decimal exclusively and follows one
consistent rounding rule.

Rounding rule (applies to every function that divides an amount across
multiple people): compute each person's floor-rounded share in whole
paise, then hand out the leftover paise one at a time, in ascending
user-id order, to the first N people (N = the remainder in paise). This
is deterministic — the same inputs always produce the same output — and
guarantees shares always sum exactly to the original amount, no matter
how badly the division rounds (see the module's test coverage for
₹100/3, ₹100/6, ₹10/3, and ₹0.01/3).
"""
from decimal import ROUND_DOWN, Decimal

from django.core.exceptions import ValidationError
from django.db import transaction as db_transaction
from django.utils import timezone

from ..models import Settlement, SettlementMode, SettlementStatus, SplitExpense

ZERO = Decimal('0.00')
CENT = Decimal('0.01')


# ================================================================================
# Split-type share math
# ================================================================================

def equal_shares(amount, participant_ids):
    """Split `amount` evenly across `participant_ids`, in whole paise."""
    n = len(participant_ids)
    if n == 0:
        return {}
    total_cents = int((amount / CENT).to_integral_value(rounding=ROUND_DOWN))
    base_cents = total_cents // n
    remainder_cents = total_cents - base_cents * n
    ordered = sorted(participant_ids)
    return {
        uid: Decimal(base_cents + (1 if i < remainder_cents else 0)) * CENT
        for i, uid in enumerate(ordered)
    }


def custom_shares(amount, participant_ids, exact_shares):
    """Validate a set of exact per-person amounts sums to `amount`. Returns
    the validated {user_id: Decimal} mapping unchanged (there's no rounding
    to do — the caller supplied exact figures)."""
    if not exact_shares:
        raise ValidationError({'exact_shares': 'Exact amounts are required for a custom split.'})
    shares = {int(uid): Decimal(str(v)) for uid, v in exact_shares.items()}
    if set(shares.keys()) != set(participant_ids):
        raise ValidationError({'exact_shares': 'Exact amounts must be provided for exactly the selected participants.'})
    if any(v < 0 for v in shares.values()):
        raise ValidationError({'exact_shares': 'Shares cannot be negative.'})
    total = sum(shares.values())
    if total != amount:
        raise ValidationError({'exact_shares': f'Exact amounts must add up to the total (Rs.{amount}), got Rs.{total}.'})
    return shares


def percentage_shares(amount, participant_ids, percentages):
    """Split `amount` by percentage, in whole paise. Validates the
    percentages sum to exactly 100. Returns (shares, percentages_by_uid)."""
    if not percentages:
        raise ValidationError({'percentages': 'Percentages are required for a percentage split.'})
    pcts = {int(uid): Decimal(str(v)) for uid, v in percentages.items()}
    if set(pcts.keys()) != set(participant_ids):
        raise ValidationError({'percentages': 'Percentages must be provided for exactly the selected participants.'})
    if any(v < 0 for v in pcts.values()):
        raise ValidationError({'percentages': 'Percentages cannot be negative.'})
    total_pct = sum(pcts.values())
    if total_pct != Decimal('100'):
        raise ValidationError({'percentages': f'Percentages must add up to 100, got {total_pct}.'})

    ordered = sorted(pcts.keys())
    total_cents = int((amount / CENT).to_integral_value(rounding=ROUND_DOWN))
    raw_cents = {
        uid: int((amount * pcts[uid] / Decimal('100') / CENT).to_integral_value(rounding=ROUND_DOWN))
        for uid in ordered
    }
    remainder_cents = total_cents - sum(raw_cents.values())
    shares = {
        uid: Decimal(raw_cents[uid] + (1 if i < remainder_cents else 0)) * CENT
        for i, uid in enumerate(ordered)
    }
    return shares, pcts


# ================================================================================
# Pairwise netting
# ================================================================================

def net_pairwise_debts(debts):
    """Cancel mutual debts between every pair down to a single net direction
    + amount per pair.

    `debts` is an iterable of (debtor_id, creditor_id, amount) meaning
    debtor_id owes creditor_id `amount`. `amount` may be negative to
    represent a reduction of an existing debt (e.g. a repayment already
    made) — see `_pairwise_net_for_group` below for how that's used.

    Example: [(A, B, 500), (B, A, 200)] -> [(A, B, 300)].
    """
    pair_balance = {}
    for debtor, creditor, amount in debts:
        amount = Decimal(str(amount))
        key = tuple(sorted((debtor, creditor)))
        # Balance tracked from key[0]'s perspective: positive means key[0] is owed.
        sign = 1 if key[0] == creditor else -1
        pair_balance[key] = pair_balance.get(key, ZERO) + sign * amount

    results = []
    for (a, b), bal in pair_balance.items():
        if abs(bal) < CENT:
            continue
        if bal > 0:
            results.append((b, a, bal))  # b owes a
        else:
            results.append((a, b, -bal))  # a owes b
    return results


# ================================================================================
# Global (debt-simplification) settlement
# ================================================================================

def simplify_global_debts(net_balances):
    """Minimize the number of payer->payee transfers needed to settle a
    group, given each person's overall net balance.

    `net_balances` is a dict {user_id: Decimal} where positive = owed
    money, negative = owes money. Balances smaller than one paisa are
    treated as already settled and ignored.

    Uses a greedy largest-debtor-vs-largest-creditor match: repeatedly
    settles as much as possible between the biggest debtor and biggest
    creditor. This is the standard "debt simplification" approach used by
    Splitwise-style apps.

    Example: {A: -500, B: -300, C: 800} -> [(A, C, 500), (B, C, 300)].
    """
    net = {uid: bal for uid, bal in net_balances.items() if abs(bal) >= CENT}
    debtors = sorted([[uid, -bal] for uid, bal in net.items() if bal < 0], key=lambda x: -x[1])
    creditors = sorted([[uid, bal] for uid, bal in net.items() if bal > 0], key=lambda x: -x[1])

    results = []
    i, j = 0, 0
    while i < len(debtors) and j < len(creditors):
        debtor_id, owes = debtors[i]
        creditor_id, owed = creditors[j]
        settle_amount = min(owes, owed)
        if settle_amount >= CENT:
            results.append((debtor_id, creditor_id, settle_amount.quantize(CENT, rounding=ROUND_DOWN)))
        debtors[i][1] -= settle_amount
        creditors[j][1] -= settle_amount
        if debtors[i][1] < CENT:
            i += 1
        if creditors[j][1] < CENT:
            j += 1
    return results


# ================================================================================
# DB-bound balance builders (feed the group's expenses into the pure functions above)
# ================================================================================

def _raw_expense_debts(group):
    """Every (ower, payer, amount) implied directly by the group's
    expenses — for each expense, every non-payer participant owes the
    payer their share. Raw input to net_pairwise_debts()."""
    debts = []
    for expense in SplitExpense.objects.filter(group=group).prefetch_related('shares'):
        payer = expense.paid_by_id
        for share in expense.shares.all():
            if share.user_id == payer or share.share_amount == ZERO:
                continue
            debts.append((share.user_id, payer, share.share_amount))
    return debts


def _per_user_totals(group):
    """One pass over the group's expenses: {user_id: {'paid': Decimal, 'share': Decimal}}."""
    totals = {}

    def bucket(uid):
        return totals.setdefault(uid, {'paid': ZERO, 'share': ZERO})

    for expense in SplitExpense.objects.filter(group=group).prefetch_related('shares'):
        bucket(expense.paid_by_id)['paid'] += expense.amount
        for share in expense.shares.all():
            bucket(share.user_id)['share'] += share.share_amount
    return totals


def _net_balances(group):
    """Overall net balance per user, including already-paid settlements:
    positive = owed money, negative = owes money."""
    balances = {uid: t['paid'] - t['share'] for uid, t in _per_user_totals(group).items()}
    for s in Settlement.objects.filter(group=group, status=SettlementStatus.PAID):
        balances[s.payer_id] = balances.get(s.payer_id, ZERO) + s.amount
        balances[s.payee_id] = balances.get(s.payee_id, ZERO) - s.amount
    return balances


def _pairwise_net_for_group(group):
    """net_pairwise_debts(), adjusted so already-paid settlements reduce the
    outstanding balance between the pair they were paid between."""
    debts = _raw_expense_debts(group)
    for s in Settlement.objects.filter(group=group, status=SettlementStatus.PAID):
        # s.payer already paid s.payee `amount`, so that debt is reduced.
        debts.append((s.payer_id, s.payee_id, -s.amount))
    return net_pairwise_debts(debts)


def _global_net_for_group(group):
    return simplify_global_debts(_net_balances(group))


# ================================================================================
# Settlement generation & lifecycle
# ================================================================================

@db_transaction.atomic
def generate_settlements(*, group):
    """Recompute settlements for a group from current expense balances.
    Clears previously-generated pending settlements and creates fresh
    ones; already-paid settlements are kept as history and factored into
    the balances above, not recalculated away."""
    Settlement.objects.filter(group=group, status=SettlementStatus.PENDING).delete()

    pairs = (
        _pairwise_net_for_group(group)
        if group.settlement_mode == SettlementMode.PAIRWISE
        else _global_net_for_group(group)
    )
    return [
        Settlement.objects.create(group=group, payer_id=payer_id, payee_id=payee_id, amount=amount)
        for payer_id, payee_id, amount in pairs
    ]


def mark_settlement_paid(*, settlement, requesting_user):
    if requesting_user.id != settlement.payee_id:
        raise ValidationError({'detail': 'Only the person who was owed money can mark a settlement as paid.'})
    if settlement.status == SettlementStatus.PAID:
        return settlement
    settlement.status = SettlementStatus.PAID
    settlement.paid_at = timezone.now()
    settlement.marked_paid_by = requesting_user
    settlement.save(update_fields=['status', 'paid_at', 'marked_paid_by'])
    return settlement


# ================================================================================
# "Show Calculation" explainability
# ================================================================================

def _display_name(user):
    return user.get_full_name() or user.username


def explain_expense(expense):
    """A human-readable breakdown of one expense: what was paid, by whom,
    each participant's share, and who owes the payer as a result.

    Matches the project's required format, e.g. for a ₹900 dinner split
    equally three ways: 'Dinner ₹900, Manav paid ₹900, Manav/Rahul/Amit
    share ₹300 each, Rahul owes Manav ₹300, Amit owes Manav ₹300'.
    """
    shares = list(expense.shares.all())
    payer_id = expense.paid_by_id
    payer_name = _display_name(expense.paid_by)
    return {
        'expense_id': expense.id,
        'description': expense.description,
        'amount': str(expense.amount),
        'paid_by': payer_name,
        'shares': [{'user': _display_name(s.user), 'amount': str(s.share_amount)} for s in shares],
        'debts': [
            {'from': _display_name(s.user), 'to': payer_name, 'amount': str(s.share_amount)}
            for s in shares if s.user_id != payer_id and s.share_amount != ZERO
        ],
    }


def explain_group(group):
    """The full calculation trail for every expense in a group, oldest first."""
    expenses = (
        SplitExpense.objects.filter(group=group)
        .order_by('expense_date', 'created_at')
        .prefetch_related('shares__user')
        .select_related('paid_by')
    )
    return [explain_expense(e) for e in expenses]


def explain_settlement(settlement):
    """Explain why a specific settlement's amount is what it is.

    PAIRWISE groups: the settlement is the direct net of expenses between
    these two people, so we point to exactly which expenses produced it.

    GLOBAL groups: the amount is a simplified, group-wide result that can
    route a debt through a third person, so it can't always be traced to
    specific expenses between just these two — instead we show the full
    group calculation trail plus each person's overall paid/share/net.
    """
    group = settlement.group
    pair_ids = {settlement.payer_id, settlement.payee_id}

    if group.settlement_mode == SettlementMode.PAIRWISE:
        expenses = (
            SplitExpense.objects.filter(group=group, paid_by_id__in=pair_ids)
            .order_by('expense_date', 'created_at')
            .prefetch_related('shares__user')
            .select_related('paid_by')
        )
        relevant = []
        for e in expenses:
            other_id = next(iter(pair_ids - {e.paid_by_id}), None)
            if other_id is None:
                continue
            if any(s.user_id == other_id and s.share_amount != ZERO for s in e.shares.all()):
                relevant.append(e)
        return {
            'mode': 'pairwise',
            'expenses': [explain_expense(e) for e in relevant],
            'note': 'This is the direct net balance between these two members.',
        }

    totals = _per_user_totals(group)
    payer_totals = totals.get(settlement.payer_id, {'paid': ZERO, 'share': ZERO})
    payee_totals = totals.get(settlement.payee_id, {'paid': ZERO, 'share': ZERO})
    return {
        'mode': 'global',
        'expenses': explain_group(group),
        'payer_net': {
            'paid': str(payer_totals['paid']), 'share': str(payer_totals['share']),
            'net': str(payer_totals['paid'] - payer_totals['share']),
        },
        'payee_net': {
            'paid': str(payee_totals['paid']), 'share': str(payee_totals['share']),
            'net': str(payee_totals['paid'] - payee_totals['share']),
        },
        'note': (
            'This group uses fewest-payments mode: the settlement above is a '
            'simplified, group-wide result, not necessarily tied to a single '
            'expense between these two people.'
        ),
    }
