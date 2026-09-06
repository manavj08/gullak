from datetime import date, timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase

from . import services

User = get_user_model()


def make_user(email='u@example.com'):
    return User.objects.create_user(username=email.split('@')[0], email=email, password='StrongPass123!')


class StreakTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.day1 = date(2026, 7, 20)
        self.day2 = self.day1 + timedelta(days=1)
        self.day3 = self.day1 + timedelta(days=2)

    def test_transaction_day_then_checkin_day_continues_streak(self):
        services.record_check_in(user=self.user, local_date=self.day1, had_transaction=True)
        services.record_check_in(user=self.user, local_date=self.day2, is_manual=True)
        streak = services.compute_current_streak(user=self.user, as_of_date=self.day2)
        self.assertEqual(streak, 2)

    def test_missed_day_breaks_streak(self):
        services.record_check_in(user=self.user, local_date=self.day1, had_transaction=True)
        # day2 skipped entirely
        streak = services.compute_current_streak(user=self.user, as_of_date=self.day3)
        self.assertEqual(streak, 0)

    def test_streak_still_alive_if_today_not_yet_checked_in_but_yesterday_was(self):
        services.record_check_in(user=self.user, local_date=self.day1, had_transaction=True)
        # as_of day2, no check-in yet today - streak should still count yesterday's as "alive"
        streak = services.compute_current_streak(user=self.user, as_of_date=self.day2)
        self.assertEqual(streak, 1)

    def test_idempotent_checkin_does_not_duplicate(self):
        services.record_check_in(user=self.user, local_date=self.day1, had_transaction=True)
        services.record_check_in(user=self.user, local_date=self.day1, is_manual=True)
        from .models import DailyCheckIn
        self.assertEqual(DailyCheckIn.objects.filter(user=self.user, date=self.day1).count(), 1)
        obj = DailyCheckIn.objects.get(user=self.user, date=self.day1)
        self.assertTrue(obj.had_transaction)
        self.assertTrue(obj.is_manual_checkin)

    def test_zero_activity_user_has_zero_streak(self):
        streak = services.compute_current_streak(user=self.user, as_of_date=self.day1)
        self.assertEqual(streak, 0)
