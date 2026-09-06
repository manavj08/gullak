from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction as db_transaction
from django.db.models import Sum

from wallet.services import compute_gullak_total
from .models import Goal, GoalStatus, PendingGoalDeduction, GoalContribution, ZERO


def total_allocated(user, exclude_goal_id=None) -> Decimal:
    """Personal-Gullak-funded goals only (funding_shared_account_id is null) — used to cap
    against the user's own Gullak total. Common goals are capped separately, per shared account."""
    qs = Goal.objects.filter(user=user, funding_shared_account_id__isnull=True)
    if exclude_goal_id:
        qs = qs.exclude(pk=exclude_goal_id)
    return qs.aggregate(total=Sum('allocated_amount'))['total'] or ZERO


def unallocated_gullak(user) -> Decimal:
    """Personal Gullak total minus what's already allocated to personal goals. This is the
    hard cap for the smart split suggestion — a suggested split can never ask the user to
    commit more than what's actually sitting unallocated in their Gullak right now."""
    return compute_gullak_total(user) - total_allocated(user)


def total_allocated_for_shared_account(shared_account_id, exclude_goal_id=None) -> Decimal:
    """Sum of allocated_amount across all common goals funded from one specific shared account."""
    qs = Goal.objects.filter(funding_shared_account_id=shared_account_id)
    if exclude_goal_id:
        qs = qs.exclude(pk=exclude_goal_id)
    return qs.aggregate(total=Sum('allocated_amount'))['total'] or ZERO


def underfunded_goals_for_deduction(user):
    """Personal-Gullak-funded goals only — common goals are never touched by an individual's
    emergency unblock, since a shared account's pool is separate from any one member's Gullak."""
    return Goal.objects.filter(user=user, funding_shared_account_id__isnull=True)


@db_transaction.atomic
def add_funds_to_goal(*, user, goal: Goal, add_amount: Decimal, contributor=None):
    """
    Increases a goal's allocated_amount by add_amount (never sets it directly —
    the UI only ever offers 'add funds', per V1.1 scope).

    Personal goals (funding_source='personal_gullak') are capped against the user's live
    Gullak total. Common goals (funding_source='shared_account') are capped against the
    shared account's pooled balance instead — personal Gullak can never fund a common goal
    and a common goal can never draw from personal Gullak (V2 "no cross-funding" rule).

    `contributor` is who is actually funding this addition — for a common goal this may be
    any member of the shared account, not just the goal's `user` (its creator). Defaults to
    `user` for the personal-goal case. Tracked per-contributor via GoalContribution so the
    goal's own detail page can show "you vs combined others" progress.
    """
    if add_amount <= 0:
        raise ValidationError({'add_amount': 'Amount must be positive.'})
    contributor = contributor or user

    new_allocated = goal.allocated_amount + add_amount

    if goal.is_common_goal:
        from wallet.models import Account
        try:
            shared_account = Account.objects.get(pk=goal.funding_shared_account_id)
        except Account.DoesNotExist:
            raise ValidationError({'detail': 'The shared account funding this goal no longer exists.'})
        pooled_total = shared_account.unblock_balance + shared_account.block_balance
        other_goals_total = total_allocated_for_shared_account(goal.funding_shared_account_id, exclude_goal_id=goal.pk)
        if other_goals_total + new_allocated > pooled_total:
            available = pooled_total - other_goals_total - goal.allocated_amount
            raise ValidationError({
                'add_amount': f'Not enough unallocated shared-account funds. '
                              f'You can add at most ₹{max(available, ZERO)} to this goal right now.'
            })
    else:
        gullak_total = compute_gullak_total(user)
        other_goals_total = total_allocated(user, exclude_goal_id=goal.pk)
        if other_goals_total + new_allocated > gullak_total:
            available = gullak_total - other_goals_total - goal.allocated_amount
            raise ValidationError({
                'add_amount': f'Not enough unallocated Gullak funds. '
                              f'You can add at most ₹{max(available, ZERO)} to this goal right now.'
            })

    goal.allocated_amount = new_allocated
    goal.status = GoalStatus.ON_TRACK
    if goal.target_amount and goal.allocated_amount >= goal.target_amount:
        goal.is_achieved = True
    goal.save(update_fields=['allocated_amount', 'status', 'is_achieved', 'updated_at'])

    if goal.is_common_goal:
        contribution, _ = GoalContribution.objects.select_for_update().get_or_create(
            goal=goal, user=contributor, defaults={'contributed_amount': ZERO}
        )
        contribution.contributed_amount = contribution.contributed_amount + add_amount
        contribution.save(update_fields=['contributed_amount'])

    return goal


def get_visible_goal_contributions(*, goal: Goal, requesting_user):
    """
    Aggregate-only visibility for a common goal's progress, mirroring the same rule
    already enforced for shared-account pool visibility (social.services.get_visible_
    contributions): the requesting member's own contribution toward THIS goal is shown
    in full, every other member's is folded into one combined figure. Never a per-member
    breakdown.
    """
    contributions = GoalContribution.objects.filter(goal=goal)
    own = next((c.contributed_amount for c in contributions if c.user_id == requesting_user.id), ZERO)
    others_aggregate = sum(
        (c.contributed_amount for c in contributions if c.user_id != requesting_user.id), ZERO
    )
    return {'own_contribution': own, 'others_aggregate': others_aggregate}


def unallocated_for_shared_account(shared_account_id) -> Decimal:
    """Shared account's pooled total minus what's already allocated to common goals funded
    from it — the equivalent cap for shared-account-funded suggestions."""
    from wallet.models import Account
    try:
        account = Account.objects.get(pk=shared_account_id)
    except Account.DoesNotExist:
        return ZERO
    pooled_total = account.unblock_balance + account.block_balance
    return pooled_total - total_allocated_for_shared_account(shared_account_id)


def common_goals_for_shared_account(shared_account_id):
    return Goal.objects.filter(funding_shared_account_id=shared_account_id)


def _urgency_candidates(goals_qs, today):
    candidates = []
    for goal in goals_qs:
        if goal.is_achieved or not goal.deadline:
            continue
        remaining = goal.target_amount - goal.allocated_amount
        days_left = (goal.deadline - today).days
        if remaining <= 0 or days_left <= 0:
            continue
        score = remaining / Decimal(days_left)
        candidates.append({'goal': goal, 'score': score, 'remaining': remaining})
    return candidates


def _split_amount_across(candidates, amount: Decimal, funding_source: str):
    if not candidates:
        return []
    total_score = sum((c['score'] for c in candidates), Decimal('0'))
    if total_score <= 0:
        return []
    results = []
    running_total = ZERO
    for i, c in enumerate(candidates):
        if i == len(candidates) - 1:
            share = amount - running_total  # last item absorbs any rounding remainder
        else:
            share = (amount * c['score'] / total_score).quantize(Decimal('0.01'))
        share = min(share, c['remaining'])  # never suggest more than a goal actually needs
        share = max(share, ZERO)
        running_total += share
        results.append({
            'goal_id': c['goal'].id,
            'goal_name': c['goal'].name,
            'suggested_amount': share,
            'funding_source': funding_source,
        })
    return results


def compute_urgency_split(user, new_amount: Decimal, shared_account_ids=None):
    """
    V2 Smart Gullak-Split Suggestion:
        urgency_score(goal) = (target_amount - allocated_amount) / days_until_deadline
    Returns a list of {goal_id, goal_name, suggested_amount, funding_source} proportional
    to each underfunded, non-achieved goal's urgency score. Goals with no deadline or
    already at/above target are excluded. This is a suggestion only — callers must still
    go through add_funds_to_goal to actually apply it, and the user can override any
    amount before confirming.

    `new_amount` is capped at the user's live unallocated Gullak total — the suggestion
    will never ask to commit more personal money than is actually sitting unallocated.

    If `shared_account_ids` is given, common goals funded from those specific shared
    accounts are included as a *separate* split, each capped against that shared
    account's own unallocated pool — never mixed with or drawn from personal Gullak
    (keeps the no-cross-funding rule intact even inside one suggestion response).
    """
    from django.utils import timezone
    today = timezone.localdate()

    capped_personal_amount = min(new_amount, unallocated_gullak(user))
    personal_candidates = _urgency_candidates(underfunded_goals_for_deduction(user), today)
    results = _split_amount_across(personal_candidates, max(capped_personal_amount, ZERO), 'personal_gullak')

    for shared_account_id in (shared_account_ids or []):
        shared_amount = min(new_amount, unallocated_for_shared_account(shared_account_id))
        shared_candidates = _urgency_candidates(common_goals_for_shared_account(shared_account_id), today)
        results += _split_amount_across(shared_candidates, max(shared_amount, ZERO), f'shared_account:{shared_account_id}')

    return results


@db_transaction.atomic
def delete_goal(*, user, goal: Goal):
    """Deleting a goal returns its allocated amount to 'unallocated' (nothing else to do — it's derived)."""
    goal.delete()


def list_pending_deductions(user):
    """Legacy: unresolved deductions awaiting manual resolution. Under V2's auto-deduct flow,
    new deductions are created pre-resolved, so this will normally be empty going forward —
    kept functional in case it's ever needed again."""
    return PendingGoalDeduction.objects.filter(user=user, resolved=False)


@db_transaction.atomic
def auto_apply_deduction(*, user, amount: Decimal, source_transaction=None):
    """
    V2 Section 5 (auto-deduct on emergency unblock, replacing V1's manual-resolution
    default): when an emergency unblock eats into goal-allocated funds, the overage is
    spread across the user's underfunded personal goals *automatically*, proportional to
    each goal's currently allocated_amount — no user action required.

    Per the confirmed V2 approach: still records a PendingGoalDeduction row for history/
    audit, but creates it already resolved (informational only, nothing left to action),
    and fires an informational Notification so the user can see what happened. Common
    (shared-account-funded) goals are never touched here — only personal Gullak goals.
    """
    from django.utils import timezone

    deduction = PendingGoalDeduction.objects.create(
        user=user, amount=amount, source_transaction=source_transaction,
    )

    goals = list(
        underfunded_goals_for_deduction(user).filter(allocated_amount__gt=0).select_for_update()
    )
    total_allocated_now = sum((g.allocated_amount for g in goals), ZERO)

    applied = []
    if goals and total_allocated_now > 0:
        remaining_to_apply = amount
        for i, goal in enumerate(goals):
            if i == len(goals) - 1:
                share = remaining_to_apply  # last goal absorbs any rounding remainder
            else:
                share = (amount * goal.allocated_amount / total_allocated_now).quantize(Decimal('0.01'))
            share = min(share, goal.allocated_amount, remaining_to_apply)
            remaining_to_apply -= share
            if share > 0:
                goal.allocated_amount = goal.allocated_amount - share
                if goal.allocated_amount < goal.target_amount:
                    goal.is_achieved = False
                    goal.status = GoalStatus.UNDERFUNDED
                goal.save(update_fields=['allocated_amount', 'status', 'is_achieved', 'updated_at'])
                applied.append({'goal_id': goal.id, 'goal_name': goal.name, 'deducted': share})

    # Informational only — nothing left for the user to resolve; recorded for history.
    deduction.resolved = True
    deduction.resolved_at = timezone.now()
    deduction.save(update_fields=['resolved', 'resolved_at'])

    from social.services import notify_goal_deduction_applied
    notify_goal_deduction_applied(user=user, amount=amount, applied=applied)

    return deduction, applied


@db_transaction.atomic
def resolve_pending_deduction(*, user, deduction: PendingGoalDeduction, allocations: list):
    """
    Applies a resolved pending deduction: `allocations` is a list of
    {'goal_id': int, 'amount': Decimal} specifying how to split the overage
    across one or more goals. The total must exactly equal deduction.amount.
    Each goal's allocated_amount is reduced by its assigned share (never below zero).
    """
    if deduction.user_id != user.id:
        raise ValidationError({'detail': 'This deduction does not belong to this user.'})
    if deduction.resolved:
        raise ValidationError({'detail': 'This deduction has already been resolved.'})

    total_assigned = sum((Decimal(str(a['amount'])) for a in allocations), ZERO)
    if total_assigned != deduction.amount:
        raise ValidationError({
            'allocations': f'Assigned amounts must add up to exactly ₹{deduction.amount} (got ₹{total_assigned}).'
        })

    goal_ids = [a['goal_id'] for a in allocations]
    goals = {g.id: g for g in Goal.objects.filter(user=user, id__in=goal_ids).select_for_update()}
    if len(goals) != len(set(goal_ids)):
        raise ValidationError({'allocations': 'One or more goals were not found for this user.'})

    for alloc in allocations:
        goal = goals[alloc['goal_id']]
        amount = Decimal(str(alloc['amount']))
        if amount < 0:
            raise ValidationError({'allocations': 'Amounts cannot be negative.'})
        if amount > goal.allocated_amount:
            raise ValidationError({
                'allocations': f'Cannot deduct ₹{amount} from "{goal.name}" — it only has ₹{goal.allocated_amount} allocated.'
            })
        goal.allocated_amount = goal.allocated_amount - amount
        if goal.allocated_amount < goal.target_amount:
            goal.is_achieved = False
        goal.save(update_fields=['allocated_amount', 'is_achieved', 'updated_at'])

    from django.utils import timezone
    deduction.resolved = True
    deduction.resolved_at = timezone.now()
    deduction.save(update_fields=['resolved', 'resolved_at'])
    return deduction
