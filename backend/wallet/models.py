from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F


class AccountCategory(models.TextChoices):
    GULLAK = 'gullak', 'Gullak'
    DAILY_TRANSACTION = 'daily_transaction', 'Daily Transaction'
    SAVINGS = 'savings', 'Savings'
    REVENUE_GENERATION = 'revenue_generation', 'Revenue Generation'
    LOAN_DEBT = 'loan_debt', 'Loan/Debt'


# Suggested account "type" values per category (free text field, these are just UI hints)
ACCOUNT_TYPE_SUGGESTIONS = {
    AccountCategory.DAILY_TRANSACTION: ['UPI', 'Cash', 'Digital Wallet'],
    AccountCategory.SAVINGS: ['Savings Account', 'Current Account'],
    AccountCategory.REVENUE_GENERATION: ['Fixed Deposit', 'Mutual Fund', 'Stocks'],
    AccountCategory.LOAN_DEBT: ['Credit Card', 'Education Loan', 'Car Loan'],
}

# Categories a user can debit from directly (spend, lend, block-out-of).
# Gullak is NOT here: money enters/leaves Gullak only via block/unblock transfers,
# never via a direct income/expense transaction.
BLOCK_CAPABLE_CATEGORIES = {AccountCategory.DAILY_TRANSACTION, AccountCategory.SAVINGS}

ZERO = Decimal('0.00')


def money_field(**kwargs):
    """Shared definition for all money fields: exact decimal rupees, 2 places."""
    defaults = dict(max_digits=12, decimal_places=2)
    defaults.update(kwargs)
    return models.DecimalField(**defaults)


class AccountOwnerType(models.TextChoices):
    """
    'individual' is the only value used in V1. V2 adds 'shared_pair' (exactly 2 people,
    no admin) and 'shared_group' (2+ people, admin-managed) — see the `social` app for
    membership, invites, and roles. A shared account's `user` field still points at its
    creator for ownership/audit purposes, but access is governed by SharedAccountMember.
    """
    INDIVIDUAL = 'individual', 'Individual'
    SHARED_PAIR = 'shared_pair', 'Shared (Relationship)'
    SHARED_GROUP = 'shared_group', 'Shared (Family & Friends Group)'


class Account(models.Model):
    """
    A financial account belonging to a user. Category determines which
    balance fields are meaningful — enforced in clean() and at the serializer layer.
    All money fields are exact Decimal rupees (2 decimal places) — never float.

    The 'gullak' category is special: exactly one is auto-created per user at
    registration, cannot be created manually or deleted by the user, and its
    balance is entirely derived from block/unblock transfers into/out of it
    (it has no direct income/expense transactions of its own).
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='accounts')
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=32, choices=AccountCategory.choices)
    account_type = models.CharField(
        max_length=50, blank=True, help_text="Free text within category, e.g. 'UPI', 'Fixed Deposit'"
    )

    # Reserved for V2 shared accounts — not built out in V1, field kept to avoid a costly future migration.
    owner_type = models.CharField(max_length=16, choices=AccountOwnerType.choices, default=AccountOwnerType.INDIVIDUAL)

    # Daily Transaction / Savings fields
    unblock_balance = money_field(default=ZERO, help_text="Spendable balance, in rupees")
    block_balance = money_field(default=ZERO, help_text="Saved/blocked balance, in rupees (unused for Gullak itself)")

    # Revenue Generation fields
    principal = money_field(null=True, blank=True, help_text="Original invested amount, in rupees")
    current_value = money_field(null=True, blank=True, help_text="Current value, in rupees")
    maturity_date = models.DateField(null=True, blank=True)

    # Loan/Debt fields
    credit_limit = money_field(null=True, blank=True, help_text="Rupees; nullable, cards only")
    amount_used = money_field(null=True, blank=True, help_text="Rupees")
    amount_owed = money_field(null=True, blank=True, help_text="Rupees")
    due_date = models.DateField(null=True, blank=True)

    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'name']
        indexes = [models.Index(fields=['user', 'category'])]
        constraints = [
            # Enforce "exactly one Gullak account per user" at the DB level, not just in application code.
            models.UniqueConstraint(
                fields=['user'], condition=models.Q(category=AccountCategory.GULLAK), name='one_gullak_per_user',
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"

    def clean(self):
        errors = {}
        if self.category == AccountCategory.GULLAK:
            pass  # Gullak's balance (unblock_balance, repurposed as "total") is fully derived — no input validation needed.
        elif self.category in BLOCK_CAPABLE_CATEGORIES:
            if self.unblock_balance < 0 or self.block_balance < 0:
                errors['unblock_balance'] = "Balances cannot be negative."
        elif self.category == AccountCategory.REVENUE_GENERATION:
            if self.principal is None or self.current_value is None:
                errors['principal'] = "Revenue Generation accounts require principal and current_value."
        elif self.category == AccountCategory.LOAN_DEBT:
            if self.amount_owed is None:
                errors['amount_owed'] = "Loan/Debt accounts require amount_owed."
        if errors:
            raise ValidationError(errors)

    @property
    def is_block_capable(self):
        return self.category in BLOCK_CAPABLE_CATEGORIES

    @property
    def is_gullak(self):
        return self.category == AccountCategory.GULLAK

    @property
    def is_shared(self):
        return self.owner_type in (AccountOwnerType.SHARED_PAIR, AccountOwnerType.SHARED_GROUP)

    @property
    def net_worth_contribution(self):
        """Signed contribution to a net-worth calculation, in rupees. Gullak is counted via unblock_balance (its total)."""
        if self.category == AccountCategory.GULLAK:
            return self.unblock_balance
        if self.category in BLOCK_CAPABLE_CATEGORIES:
            return self.unblock_balance + self.block_balance
        if self.category == AccountCategory.REVENUE_GENERATION:
            return self.current_value or ZERO
        if self.category == AccountCategory.LOAN_DEBT:
            return -(self.amount_owed or ZERO)
        return ZERO

    def block_amount(self, amount: Decimal):
        """Move money from unblock -> block. Rejects if it would make unblock negative."""
        if not self.is_block_capable:
            raise ValidationError("This account category does not support block/unblock.")
        if amount <= 0:
            raise ValidationError("Amount must be positive.")
        if amount > self.unblock_balance:
            raise ValidationError("Cannot block more than the available unblock balance.")
        self.unblock_balance = F('unblock_balance') - amount
        self.block_balance = F('block_balance') + amount
        self.save(update_fields=['unblock_balance', 'block_balance', 'updated_at'])
        self.refresh_from_db()

    def unblock_amount(self, amount: Decimal):
        """Emergency unblock: move money from block -> unblock. Soft rule, always allowed if funds exist."""
        if not self.is_block_capable:
            raise ValidationError("This account category does not support block/unblock.")
        if amount <= 0:
            raise ValidationError("Amount must be positive.")
        if amount > self.block_balance:
            raise ValidationError("Cannot unblock more than the current block balance.")
        self.block_balance = F('block_balance') - amount
        self.unblock_balance = F('unblock_balance') + amount
        self.save(update_fields=['unblock_balance', 'block_balance', 'updated_at'])
        self.refresh_from_db()

    def gullak_credit(self, amount: Decimal):
        """Increase the Gullak account's total (used when money is blocked into it elsewhere)."""
        if not self.is_gullak:
            raise ValidationError("gullak_credit() only applies to the Gullak account.")
        if amount <= 0:
            raise ValidationError("Amount must be positive.")
        self.unblock_balance = F('unblock_balance') + amount
        self.save(update_fields=['unblock_balance', 'updated_at'])
        self.refresh_from_db()

    def gullak_debit(self, amount: Decimal):
        """Decrease the Gullak account's total (used when money is unblocked out of it)."""
        if not self.is_gullak:
            raise ValidationError("gullak_debit() only applies to the Gullak account.")
        if amount <= 0:
            raise ValidationError("Amount must be positive.")
        if amount > self.unblock_balance:
            raise ValidationError("Cannot remove more than the current Gullak total.")
        self.unblock_balance = F('unblock_balance') - amount
        self.save(update_fields=['unblock_balance', 'updated_at'])
        self.refresh_from_db()


class TransactionType(models.TextChoices):
    INCOME = 'income', 'Income'
    EXPENSE = 'expense', 'Expense'
    TRANSFER = 'transfer', 'Transfer'
    LEND = 'lend', 'Lend'
    BORROW = 'borrow', 'Borrow'
    GULLAK_BLOCK = 'gullak_block', 'Gullak Block'
    GULLAK_UNBLOCK = 'gullak_unblock', 'Gullak Unblock'


class TransactionCategory(models.TextChoices):
    FOOD = 'food', 'Food'
    TRANSPORT = 'transport', 'Transport'
    BILLS = 'bills', 'Bills'
    SHOPPING = 'shopping', 'Shopping'
    OTHER = 'other', 'Other'
    UNCATEGORIZED = 'uncategorized', 'Uncategorized'


class Transaction(models.Model):
    """
    A single ledger entry affecting an account's unblock_balance.
    Income/borrow increase it; expense/lend decrease it.
    Transfer moves between two of the user's own accounts (modeled as two rows via `transfer_pair`).

    gullak_block / gullak_unblock are the two legs of moving money into/out of the
    Gullak account. They are real Transaction rows (so the Gullak account has a
    full history), but are excluded from the general Transactions list via the
    `is_gullak_leg` property / API filtering — they only appear on the Gullak
    account's own detail page.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='transactions')
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='transactions')
    type = models.CharField(max_length=20, choices=TransactionType.choices)
    amount = money_field(validators=[MinValueValidator(Decimal('0.01'))],
                          help_text="Always positive, in rupees. Direction is determined by `type`.")
    category = models.CharField(
        max_length=20, choices=TransactionCategory.choices, default=TransactionCategory.UNCATEGORIZED
    )
    note = models.CharField(max_length=255, blank=True)
    settled = models.BooleanField(default=False, help_text="Lend/borrow only — manually marked settled.")
    transfer_pair = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
        help_text="For transfer/gullak_block/gullak_unblock: links the two legs of the same movement."
    )
    # Idempotency: client generates a UUID per submission to prevent duplicate-submit issues.
    client_request_id = models.CharField(max_length=64, null=True, blank=True)

    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['account', 'timestamp']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'client_request_id'],
                name='unique_client_request_per_user',
                condition=models.Q(client_request_id__isnull=False),
            )
        ]

    def __str__(self):
        return f"{self.type} ₹{self.amount} on {self.account}"

    @property
    def is_gullak_leg(self):
        return self.type in (TransactionType.GULLAK_BLOCK, TransactionType.GULLAK_UNBLOCK)
