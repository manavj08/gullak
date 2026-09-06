from django.conf import settings
from django.db import models


class DailyCheckIn(models.Model):
    """
    One row per user per calendar day (in the user's local date, passed by the client)
    that either had a transaction or an explicit check-in. Using a date field (not
    datetime) sidesteps timezone drift for "what day is this" — the client is
    responsible for sending the correct local date; the server just stores it and
    enforces one row per (user, date).
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='check_ins')
    date = models.DateField()
    had_transaction = models.BooleanField(default=False)
    is_manual_checkin = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']
        constraints = [
            models.UniqueConstraint(fields=['user', 'date'], name='unique_checkin_per_user_per_day')
        ]

    def __str__(self):
        return f"{self.user} - {self.date}"
