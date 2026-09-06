from datetime import timedelta
from .models import DailyCheckIn


def record_check_in(*, user, local_date, had_transaction=False, is_manual=False):
    """
    Idempotent: calling this multiple times for the same (user, local_date) just
    upgrades had_transaction/is_manual flags rather than erroring or duplicating.
    `local_date` must be a date object representing the user's local calendar day
    (client sends this — avoids server-timezone assumptions, per QA flag on timezone edge cases).
    """
    obj, created = DailyCheckIn.objects.get_or_create(
        user=user, date=local_date,
        defaults={'had_transaction': had_transaction, 'is_manual_checkin': is_manual},
    )
    if not created:
        changed = False
        if had_transaction and not obj.had_transaction:
            obj.had_transaction = True
            changed = True
        if is_manual and not obj.is_manual_checkin:
            obj.is_manual_checkin = True
            changed = True
        if changed:
            obj.save(update_fields=['had_transaction', 'is_manual_checkin'])
    return obj


def compute_current_streak(*, user, as_of_date) -> int:
    """
    Counts consecutive days ending at as_of_date (or the most recent checked-in day)
    with a DailyCheckIn row. A gap of a full day with no row breaks the streak.
    """
    check_in_dates = set(
        DailyCheckIn.objects.filter(user=user, date__lte=as_of_date).values_list('date', flat=True)
    )
    if not check_in_dates:
        return 0

    # Streak must include today or yesterday to still be "alive"; otherwise it's broken (0).
    if as_of_date not in check_in_dates and (as_of_date - timedelta(days=1)) not in check_in_dates:
        return 0

    streak = 0
    cursor = as_of_date if as_of_date in check_in_dates else as_of_date - timedelta(days=1)
    while cursor in check_in_dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak
