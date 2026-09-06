"""
Business logic kept out of views/serializers so both DRF views and (future)
management commands / Android-facing endpoints can reuse identical rules.

All money is Decimal rupees (2 decimal places) — never float — end to end.
"""
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction as db_transaction
from django.db.models import Sum
from django.utils import timezone as dj_timezone

from .models import (
    Account, AccountCategory, Transaction, TransactionCategory, TransactionType,
    BLOCK_CAPABLE_CATEGORIES, ZERO,
)


def get_or_create_gullak(user) -> Account:
    """Every user has exactly one Gullak account, created at registration. This is a
    defensive fallback (e.g. for users created before this feature, or via createsuperuser)."""
    account, _ = Account.objects.get_or_create(
        user=user, category=AccountCategory.GULLAK,
        defaults={'name': 'Gullak', 'account_type': '', 'unblock_balance': ZERO, 'block_balance': ZERO},
    )
    return account


def compute_gullak_total(user) -> Decimal:
    """Gullak total is simply the Gullak account's own running balance — always live, never recomputed from other tables."""
    gullak = get_or_create_gullak(user)
    return gullak.unblock_balance


def compute_net_worth(user) -> Decimal:
    accounts = Account.objects.filter(user=user, is_archived=False)
    return sum((a.net_worth_contribution for a in accounts), ZERO)


# ================================================================================
# Analytics: Net Worth Over Time & Spend by Category
# ================================================================================

def net_worth_history(user, days: int = 30) -> list:
    """
    Net worth for each of the last `days` days (oldest first), e.g.:
    [{'date': '2026-08-01', 'net_worth': Decimal('25000.00')}, ...]

    Daily Transaction / Savings / Gullak balances are reconstructed exactly,
    by taking today's net worth and reversing each day's income/expense/
    lend/borrow transactions back off it (transfers and Gullak block/unblock
    move money between the user's own accounts, so they net to zero across
    the total and don't need reversing).

    Revenue Generation (current_value) and Loan/Debt (amount_owed) accounts
    have no dated transaction history in this app — they're direct fields,
    not built from a ledger — so their *current* value is held constant
    across every day in the range. This is a documented approximation, not
    a claim those balances were literally unchanged historically.
    """
    today = dj_timezone.localdate()
    start_date = today - timedelta(days=days - 1)
    current_net_worth = compute_net_worth(user)

    relevant_types = [
        TransactionType.EXPENSE, TransactionType.INCOME, TransactionType.LEND, TransactionType.BORROW,
    ]
    txns = Transaction.objects.filter(
        user=user, type__in=relevant_types, timestamp__date__gte=start_date,
    ).values('timestamp', 'type', 'amount')

    effect_by_date = {}
    for t in txns:
        d = dj_timezone.localtime(t['timestamp']).date()
        if d > today:
            continue
        delta = t['amount'] if t['type'] in (TransactionType.INCOME, TransactionType.BORROW) else -t['amount']
        effect_by_date[d] = effect_by_date.get(d, ZERO) + delta

    history = []
    running_after = ZERO  # sum of effects for dates strictly after the one about to be computed
    d = today
    while d >= start_date:
        history.append({'date': d.isoformat(), 'net_worth': current_net_worth - running_after})
        running_after += effect_by_date.get(d, ZERO)
        d -= timedelta(days=1)

    history.reverse()  # oldest first
    return history


def spend_by_category(user, days: int = 30) -> list:
    """
    Total EXPENSE amount per category over the last `days` days, largest
    first, e.g. [{'category': 'Food', 'amount': Decimal('5000.00')}, ...].
    Categories with no spending in the period are omitted (not returned as zero).
    """
    today = dj_timezone.localdate()
    start_date = today - timedelta(days=days - 1)
    category_labels = dict(TransactionCategory.choices)

    rows = (
        Transaction.objects.filter(user=user, type=TransactionType.EXPENSE, timestamp__date__gte=start_date)
        .values('category')
        .annotate(amount=Sum('amount'))
        .order_by('-amount')
    )
    return [
        {
            'category': category_labels.get(row['category'], row['category']),
            'amount': row['amount'].quantize(Decimal('0.01')),
        }
        for row in rows
    ]


@db_transaction.atomic
def create_transaction(*, user, account: Account, type_: str, amount: Decimal, category=None,
                        note='', client_request_id=None) -> Transaction:
    """
    Creates a transaction and applies its effect on the account's unblock_balance.
    Idempotent via client_request_id (double-submit protection).
    """
    if amount <= 0:
        raise ValidationError({'amount': 'Amount must be positive.'})
    if account.user_id != user.id:
        raise ValidationError({'account': 'Account does not belong to this user.'})
    if account.category == AccountCategory.GULLAK:
        raise ValidationError({'account': 'Use block/emergency-unblock for the Gullak account, not direct transactions.'})

    if client_request_id:
        existing = Transaction.objects.filter(user=user, client_request_id=client_request_id).first()
        if existing:
            return existing

    account = Account.objects.select_for_update().get(pk=account.pk)

    if type_ in (TransactionType.EXPENSE, TransactionType.LEND):
        if amount > account.unblock_balance:
            raise ValidationError({'amount': 'Insufficient available (unblock) balance.'})
        account.unblock_balance = account.unblock_balance - amount
    elif type_ in (TransactionType.INCOME, TransactionType.BORROW):
        account.unblock_balance = account.unblock_balance + amount
    else:
        raise ValidationError({'type': 'Use create_transfer() for transfer type.'})

    account.save(update_fields=['unblock_balance', 'updated_at'])

    txn = Transaction.objects.create(
        user=user, account=account, type=type_, amount=amount,
        category=category or 'uncategorized', note=note, client_request_id=client_request_id,
    )
    return txn


@db_transaction.atomic
def create_transfer(*, user, from_account: Account, to_account: Account, amount: Decimal,
                     note='', client_request_id=None) -> Transaction:
    """Transfer between two of the user's own accounts (excluding Gullak — use block/unblock for that)."""
    if amount <= 0:
        raise ValidationError({'amount': 'Amount must be positive.'})
    if from_account.pk == to_account.pk:
        raise ValidationError({'to_account': 'Cannot transfer to the same account.'})
    if from_account.user_id != user.id or to_account.user_id != user.id:
        raise ValidationError({'account': 'Both accounts must belong to this user.'})
    if from_account.category == AccountCategory.GULLAK or to_account.category == AccountCategory.GULLAK:
        raise ValidationError({'account': 'Use block/emergency-unblock to move money in or out of Gullak.'})

    if client_request_id:
        existing = Transaction.objects.filter(user=user, client_request_id=client_request_id).first()
        if existing:
            return existing

    from_account = Account.objects.select_for_update().get(pk=from_account.pk)
    to_account = Account.objects.select_for_update().get(pk=to_account.pk)

    if amount > from_account.unblock_balance:
        raise ValidationError({'amount': 'Insufficient available (unblock) balance in source account.'})

    from_account.unblock_balance = from_account.unblock_balance - amount
    to_account.unblock_balance = to_account.unblock_balance + amount
    from_account.save(update_fields=['unblock_balance', 'updated_at'])
    to_account.save(update_fields=['unblock_balance', 'updated_at'])

    out_txn = Transaction.objects.create(
        user=user, account=from_account, type=TransactionType.TRANSFER, amount=amount,
        note=note, client_request_id=client_request_id,
    )
    in_txn = Transaction.objects.create(
        user=user, account=to_account, type=TransactionType.TRANSFER, amount=amount,
        note=note, transfer_pair=out_txn,
    )
    out_txn.transfer_pair = in_txn
    out_txn.save(update_fields=['transfer_pair'])
    return out_txn


@db_transaction.atomic
def contribute_to_shared_account(*, user, from_account: Account, shared_account: Account,
                                  amount: Decimal, client_request_id=None):
    """
    V2: moves money from one of the user's own block-capable accounts into a shared
    (pair/group) account's pooled balance, and records the contribution against that
    member specifically (social.SharedContribution) — this is what makes "unblock only
    your own portion" and the itemized-vs-aggregate visibility rule enforceable.
    """
    from social.models import SharedAccountMember, SharedContribution

    if from_account.user_id != user.id:
        raise ValidationError({'from_account': 'Account does not belong to this user.'})
    if not from_account.is_block_capable:
        raise ValidationError({'from_account': 'This account category cannot fund a shared account.'})
    if not shared_account.is_shared:
        raise ValidationError({'shared_account': 'Target is not a shared account.'})
    if not SharedAccountMember.objects.filter(account=shared_account, user=user).exists():
        raise ValidationError({'shared_account': 'You are not a member of this shared account.'})
    if amount <= 0:
        raise ValidationError({'amount': 'Amount must be positive.'})

    if client_request_id:
        existing = Transaction.objects.filter(user=user, client_request_id=client_request_id).first()
        if existing:
            return shared_account

    from_account = Account.objects.select_for_update().get(pk=from_account.pk)
    shared_account = Account.objects.select_for_update().get(pk=shared_account.pk)

    if amount > from_account.unblock_balance:
        raise ValidationError({'amount': 'Cannot contribute more than the available unblock balance.'})

    from_account.unblock_balance = from_account.unblock_balance - amount
    from_account.save(update_fields=['unblock_balance', 'updated_at'])
    shared_account.block_balance = shared_account.block_balance + amount
    shared_account.save(update_fields=['block_balance', 'updated_at'])

    out_txn = Transaction.objects.create(
        user=user, account=from_account, type=TransactionType.GULLAK_BLOCK, amount=amount,
        note=f'Contributed to {shared_account.name}', client_request_id=client_request_id,
    )
    in_txn = Transaction.objects.create(
        user=user, account=shared_account, type=TransactionType.GULLAK_BLOCK, amount=amount,
        note=f'Contribution from {user.username}', transfer_pair=out_txn,
    )
    out_txn.transfer_pair = in_txn
    out_txn.save(update_fields=['transfer_pair'])

    contribution, _ = SharedContribution.objects.select_for_update().get_or_create(
        account=shared_account, user=user, defaults={'contributed_amount': ZERO}
    )
    contribution.contributed_amount = contribution.contributed_amount + amount
    contribution.save(update_fields=['contributed_amount'])

    return shared_account


@db_transaction.atomic
def emergency_unblock_own_share(*, user, shared_account: Account, to_account: Account,
                                 amount: Decimal, client_request_id=None):
    """
    V2 Section 5/7: a shared-account member can only unblock their OWN contributed
    portion — never the pooled total or another member's share. Capped at the member's
    live SharedContribution.contributed_amount. No consent step required, since a member
    acting on their own contribution needs no one else's approval.
    """
    from social.models import SharedAccountMember, SharedContribution

    if not shared_account.is_shared:
        raise ValidationError({'shared_account': 'Not a shared account.'})
    if not SharedAccountMember.objects.filter(account=shared_account, user=user).exists():
        raise ValidationError({'shared_account': 'You are not a member of this shared account.'})
    if to_account.user_id != user.id or not to_account.is_block_capable:
        raise ValidationError({'to_account': 'Invalid destination account.'})
    if amount <= 0:
        raise ValidationError({'amount': 'Amount must be positive.'})

    if client_request_id:
        existing = Transaction.objects.filter(user=user, client_request_id=client_request_id).first()
        if existing:
            return shared_account

    shared_account = Account.objects.select_for_update().get(pk=shared_account.pk)
    to_account = Account.objects.select_for_update().get(pk=to_account.pk)
    contribution = SharedContribution.objects.select_for_update().filter(
        account=shared_account, user=user
    ).first()
    own_contributed = contribution.contributed_amount if contribution else ZERO

    if amount > own_contributed:
        raise ValidationError({
            'amount': f'You can only unblock your own contributed portion (₹{own_contributed} available).'
        })
    if amount > shared_account.block_balance:
        raise ValidationError({'amount': 'Cannot unblock more than the shared account currently holds.'})

    shared_account.block_balance = shared_account.block_balance - amount
    shared_account.save(update_fields=['block_balance', 'updated_at'])
    to_account.unblock_balance = to_account.unblock_balance + amount
    to_account.save(update_fields=['unblock_balance', 'updated_at'])
    contribution.contributed_amount = contribution.contributed_amount - amount
    contribution.save(update_fields=['contributed_amount'])

    out_txn = Transaction.objects.create(
        user=user, account=shared_account, type=TransactionType.GULLAK_UNBLOCK, amount=amount,
        note=f'{user.username} unblocked own share to {to_account.name}', client_request_id=client_request_id,
    )
    in_txn = Transaction.objects.create(
        user=user, account=to_account, type=TransactionType.GULLAK_UNBLOCK, amount=amount,
        note=f'Emergency unblock from {shared_account.name}', transfer_pair=out_txn,
    )
    out_txn.transfer_pair = in_txn
    out_txn.save(update_fields=['transfer_pair'])

    return shared_account


@db_transaction.atomic
def block_funds(*, user, account: Account, amount: Decimal, client_request_id=None):
    """
    Moves money from a Daily Transaction / Savings account's unblock_balance
    into the Gullak account. Recorded as two linked Transaction rows
    (gullak_block on the source account, gullak_block on the Gullak account)
    so the Gullak page has a full history, but these are excluded from the
    general Transactions list via `is_gullak_leg`.
    """
    if account.user_id != user.id:
        raise ValidationError({'account': 'Account does not belong to this user.'})
    if not account.is_block_capable:
        raise ValidationError({'account': 'This account category does not support blocking funds.'})
    if amount <= 0:
        raise ValidationError({'amount': 'Amount must be positive.'})

    if client_request_id:
        existing = Transaction.objects.filter(user=user, client_request_id=client_request_id).first()
        if existing:
            return get_or_create_gullak(user)

    account = Account.objects.select_for_update().get(pk=account.pk)
    gullak = Account.objects.select_for_update().get(pk=get_or_create_gullak(user).pk)

    if amount > account.unblock_balance:
        raise ValidationError({'amount': 'Cannot block more than the available unblock balance.'})

    account.unblock_balance = account.unblock_balance - amount
    account.save(update_fields=['unblock_balance', 'updated_at'])
    gullak.unblock_balance = gullak.unblock_balance + amount
    gullak.save(update_fields=['unblock_balance', 'updated_at'])

    out_txn = Transaction.objects.create(
        user=user, account=account, type=TransactionType.GULLAK_BLOCK, amount=amount,
        note='Blocked into Gullak', client_request_id=client_request_id,
    )
    in_txn = Transaction.objects.create(
        user=user, account=gullak, type=TransactionType.GULLAK_BLOCK, amount=amount,
        note=f'Blocked from {account.name}', transfer_pair=out_txn,
    )
    out_txn.transfer_pair = in_txn
    out_txn.save(update_fields=['transfer_pair'])
    return gullak


@db_transaction.atomic
def emergency_unblock_funds(*, user, account: Account, amount: Decimal, client_request_id=None):
    """
    Moves money from the Gullak account back into a Daily Transaction / Savings
    account's unblock_balance. Soft rule: always allowed if Gullak has the funds.

    If the unblocked amount is fully covered by *unallocated* Gullak funds, nothing
    else happens. If it eats into goal-allocated funds, a PendingGoalDeduction is
    created instead of silently touching any goal — the user resolves it on Home.
    """
    if account.user_id != user.id:
        raise ValidationError({'account': 'Account does not belong to this user.'})
    if not account.is_block_capable:
        raise ValidationError({'account': 'This account category cannot receive unblocked funds.'})
    if amount <= 0:
        raise ValidationError({'amount': 'Amount must be positive.'})

    if client_request_id:
        existing = Transaction.objects.filter(user=user, client_request_id=client_request_id).first()
        if existing:
            return get_or_create_gullak(user)

    account = Account.objects.select_for_update().get(pk=account.pk)
    gullak = Account.objects.select_for_update().get(pk=get_or_create_gullak(user).pk)

    if amount > gullak.unblock_balance:
        raise ValidationError({'amount': 'Cannot unblock more than the current Gullak total.'})

    # Determine overage against unallocated funds BEFORE mutating balances.
    from goals.services import total_allocated
    allocated = total_allocated(user)
    unallocated = gullak.unblock_balance - allocated
    overage = amount - unallocated if amount > unallocated else ZERO

    gullak.unblock_balance = gullak.unblock_balance - amount
    gullak.save(update_fields=['unblock_balance', 'updated_at'])
    account.unblock_balance = account.unblock_balance + amount
    account.save(update_fields=['unblock_balance', 'updated_at'])

    out_txn = Transaction.objects.create(
        user=user, account=gullak, type=TransactionType.GULLAK_UNBLOCK, amount=amount,
        note=f'Unblocked to {account.name}', client_request_id=client_request_id,
    )
    in_txn = Transaction.objects.create(
        user=user, account=account, type=TransactionType.GULLAK_UNBLOCK, amount=amount,
        note='Emergency unblock from Gullak', transfer_pair=out_txn,
    )
    out_txn.transfer_pair = in_txn
    out_txn.save(update_fields=['transfer_pair'])

    if overage > 0:
        # V2: automatically deduct the overage from underfunded goals proportionally,
        # rather than waiting for the user to manually resolve it. Still generates an
        # informational notification so the user sees what happened.
        from goals.services import auto_apply_deduction
        auto_apply_deduction(user=user, amount=overage, source_transaction=out_txn)

    return gullak
