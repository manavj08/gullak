from decimal import Decimal

from django.conf import settings
from django.db import models

ZERO = Decimal('0.00')


def money_field(**kwargs):
    defaults = dict(max_digits=12, decimal_places=2)
    defaults.update(kwargs)
    return models.DecimalField(**defaults)


class GoalStatus(models.TextChoices):
    ON_TRACK = 'on_track', 'On Track'
    UNDERFUNDED = 'underfunded', 'Underfunded'


class Goal(models.Model):
    """
    A savings goal. `allocated_amount` labels a slice of the user's live Gullak total —
    it is not a real fund movement, just bookkeeping/intent.
    Sum of allocated_amount across a user's goals must never exceed the Gullak total at
    allocation time (enforced in services.add_funds_to_goal / API layer).

    In V1.1, users can only ever *add* to allocated_amount via the UI (services.add_funds_to_goal).
    allocated_amount only ever decreases via an emergency-unblock overage being resolved
    against this goal (services.apply_pending_deduction), never by direct user edit.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='goals')
    name = models.CharField(max_length=100)
    item_link = models.URLField(blank=True, null=True)
    target_amount = money_field(help_text="Rupees")
    deadline = models.DateField(null=True, blank=True)
    allocated_amount = money_field(default=ZERO, help_text="Rupees, portion of Gullak assigned to this goal")
    status = models.CharField(max_length=16, choices=GoalStatus.choices, default=GoalStatus.ON_TRACK)
    is_achieved = models.BooleanField(default=False)

    # V2: a goal is funded either from the user's personal Gullak, or from exactly one
    # shared account (wallet.Account.id, stored as a plain int — not a FK, since a shared
    # account may later be left/deleted independently). Never both — enforced in services.
    # NULL/blank funding_shared_account_id means personal_gullak.
    funding_shared_account_id = models.IntegerField(
        null=True, blank=True,
        help_text="If set, this goal is a common goal funded only from this shared wallet.Account — never from personal Gullak."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.user})"

    @property
    def progress_percent(self):
        if not self.target_amount:
            return 0
        return min(100, round(float(self.allocated_amount / self.target_amount) * 100, 1))

    @property
    def funding_source(self):
        return 'shared_account' if self.funding_shared_account_id else 'personal_gullak'

    @property
    def is_common_goal(self):
        return self.funding_shared_account_id is not None


class GoalContribution(models.Model):
    """
    V2: per-member tracking of how much each shared-account member has personally put
    toward one specific common Goal (distinct from SharedContribution, which tracks a
    member's contribution to the shared account's overall pool — a shared account can
    fund several common goals, so this is scoped per-goal). Used to render the
    "you vs combined others" progress view on a common goal's detail page, following
    the same aggregate-only visibility rule as the shared account itself.
    """
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name='contributions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='goal_contributions')
    contributed_amount = money_field(default=ZERO)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['goal', 'user'], name='unique_contribution_per_goal_user')
        ]

    def __str__(self):
        return f"{self.user} contributed ₹{self.contributed_amount} to {self.goal}"


class PendingGoalDeduction(models.Model):
    """
    Created when an emergency unblock removes more from Gullak than was unallocated,
    meaning the overage effectively comes out of goal-allocated money. Rather than
    silently reducing a goal's allocation, we record the overage here and ask the
    user (on their next Home visit) which goal(s) to deduct it from.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='pending_deductions')
    amount = money_field(help_text="Rupees still needing to be assigned to a goal's reduced allocation")
    source_transaction = models.ForeignKey(
        'wallet.Transaction', on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
        help_text="The emergency-unblock leg that caused this overage."
    )
    resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Pending ₹{self.amount} deduction for {self.user}"
