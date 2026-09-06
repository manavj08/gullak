"""
Models for the splits app: standalone Splitwise-style group expense
splitting. Independent of the wallet/social apps by design -- a SplitGroup
is a lightweight set of members, not tied to a wallet Account or balance.

All money fields use Decimal. Never use float for financial values.
"""
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


def money_field(**kwargs):
    defaults = dict(max_digits=12, decimal_places=2)
    defaults.update(kwargs)
    return models.DecimalField(**defaults)


class SettlementMode(models.TextChoices):
    GLOBAL = 'global', 'Global (simplified debts)'
    PAIRWISE = 'pairwise', 'Pairwise (direct net balances)'


class SplitGroup(models.Model):
    name = models.CharField(max_length=100)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='split_groups_created',
    )
    settlement_mode = models.CharField(
        max_length=10, choices=SettlementMode.choices, default=SettlementMode.GLOBAL,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class SplitGroupMemberRole(models.TextChoices):
    ADMIN = 'admin', 'Admin'
    MEMBER = 'member', 'Member'


class SplitGroupMember(models.Model):
    group = models.ForeignKey(SplitGroup, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='split_group_memberships',
    )
    role = models.CharField(max_length=10, choices=SplitGroupMemberRole.choices, default=SplitGroupMemberRole.MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['joined_at']
        constraints = [
            models.UniqueConstraint(fields=['group', 'user'], name='unique_split_group_member'),
        ]

    def __str__(self):
        return f'{self.user} in {self.group} ({self.role})'


class SplitType(models.TextChoices):
    EQUAL = 'equal', 'Split equally'
    CUSTOM = 'custom', 'Custom amounts'
    PERCENTAGE = 'percentage', 'Percentage split'


class SplitExpense(models.Model):
    group = models.ForeignKey(SplitGroup, on_delete=models.CASCADE, related_name='expenses')
    description = models.CharField(max_length=200)
    amount = money_field(validators=[MinValueValidator(Decimal('0.01'))])
    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='split_expenses_paid',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='split_expenses_logged',
    )
    split_type = models.CharField(max_length=12, choices=SplitType.choices, default=SplitType.EQUAL)
    expense_date = models.DateField()
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-expense_date', '-created_at']
        indexes = [models.Index(fields=['group', 'expense_date'])]

    def __str__(self):
        return f'{self.description} (Rs.{self.amount}) in {self.group}'


class SplitExpenseShare(models.Model):
    expense = models.ForeignKey(SplitExpense, on_delete=models.CASCADE, related_name='shares')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='split_expense_shares',
    )
    share_amount = money_field(validators=[MinValueValidator(Decimal('0.00'))])
    percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Only set when the expense's split_type is percentage.",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['expense', 'user'], name='unique_split_share_per_expense_user'),
        ]

    def __str__(self):
        return f'{self.user} owes Rs.{self.share_amount} for {self.expense}'


class SettlementStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    PAID = 'paid', 'Paid'


class Settlement(models.Model):
    group = models.ForeignKey(SplitGroup, on_delete=models.CASCADE, related_name='settlements')
    payer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='split_settlements_to_pay',
    )
    payee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='split_settlements_to_receive',
    )
    amount = money_field(validators=[MinValueValidator(Decimal('0.01'))])
    status = models.CharField(max_length=10, choices=SettlementStatus.choices, default=SettlementStatus.PENDING)
    generated_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    marked_paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )

    class Meta:
        ordering = ['-generated_at']
        indexes = [models.Index(fields=['group', 'status'])]

    def __str__(self):
        return f'{self.payer} owes {self.payee} Rs.{self.amount} ({self.status})'
