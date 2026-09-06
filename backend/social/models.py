from django.conf import settings
from django.db import models


class SharedAccountRole(models.TextChoices):
    MEMBER = 'member', 'Member'
    ADMIN = 'admin', 'Admin'


class SharedAccountMember(models.Model):
    """
    Membership row linking a user to a shared (pair or group) wallet.Account.
    A 2-person 'shared_pair' account has exactly two members, neither an admin
    (V2 spec: "no admin concept needed — two equal partners"). A 'shared_group'
    account has an admin (creator by default, promotable) plus members.
    """
    account = models.ForeignKey('wallet.Account', on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='shared_memberships')
    role = models.CharField(max_length=16, choices=SharedAccountRole.choices, default=SharedAccountRole.MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['joined_at']
        constraints = [
            models.UniqueConstraint(fields=['account', 'user'], name='unique_member_per_account')
        ]

    def __str__(self):
        return f"{self.user} in {self.account} ({self.role})"


class GroupInviteStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    ACCEPTED = 'accepted', 'Accepted'
    DECLINED = 'declined', 'Declined'


class GroupInvite(models.Model):
    """
    An invite to join a shared/group account, looked up by username (never phone/email —
    per V2's confirmed privacy-preserving invite flow). The invited user must explicitly
    accept before the account/membership is created (pair) or before they're added (group).
    """
    account = models.ForeignKey('wallet.Account', on_delete=models.CASCADE, related_name='invites')
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_invites'
    )
    invited_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_invites'
    )
    status = models.CharField(max_length=16, choices=GroupInviteStatus.choices, default=GroupInviteStatus.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            # A user can't have two simultaneous pending invites to the same account.
            models.UniqueConstraint(
                fields=['account', 'invited_user'],
                condition=models.Q(status='pending'),
                name='unique_pending_invite_per_account_user',
            )
        ]

    def __str__(self):
        return f"Invite to {self.invited_user} for {self.account} ({self.status})"


class GroupOccasion(models.Model):
    """Optional occasion metadata for a 'shared_group' account (e.g. 'Goa Trip Fund')."""
    account = models.OneToOneField('wallet.Account', on_delete=models.CASCADE, related_name='occasion')
    name = models.CharField(max_length=100)
    occasion_date = models.DateField(null=True, blank=True)
    reminder_enabled = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class AdminTransferStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    ACCEPTED = 'accepted', 'Accepted'
    DECLINED = 'declined', 'Declined'


class AdminTransferRequest(models.Model):
    """Promote-another-member-to-admin request, so promotion is consent-based and auditable."""
    account = models.ForeignKey('wallet.Account', on_delete=models.CASCADE, related_name='admin_transfer_requests')
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_admin_transfers'
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_admin_transfers'
    )
    status = models.CharField(max_length=16, choices=AdminTransferStatus.choices, default=AdminTransferStatus.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Admin transfer: {self.target_user} for {self.account} ({self.status})"


class SharedContribution(models.Model):
    """
    Running total of how much a given member has personally contributed (net of their
    own emergency unblocks) into a shared account's pooled balance. This is what makes
    the visibility rule and the "unblock only your own portion" rule enforceable:
    - Each member sees their own `contributed_amount` in full (itemized).
    - Other members' contributions are only ever exposed as one aggregate sum.
    - Emergency unblock on a shared account is capped at the requesting member's own
      `contributed_amount`, never the pooled total or another member's share.
    Leaving/removal does not zero this out — per the confirmed decision, an already
    -contributed amount stays part of the pooled total even after a member leaves.
    """
    account = models.ForeignKey('wallet.Account', on_delete=models.CASCADE, related_name='contributions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='shared_contributions')
    contributed_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['account', 'user'], name='unique_contribution_per_account_user')
        ]

    def __str__(self):
        return f"{self.user} contributed ₹{self.contributed_amount} to {self.account}"


class NotificationType(models.TextChoices):
    INVITE = 'invite', 'Invite'
    ADMIN_TRANSFER = 'admin_transfer', 'Admin Transfer'
    REMINDER = 'reminder', 'Reminder'
    GOAL_UNDERFUNDED = 'goal_underfunded', 'Goal Underfunded'
    MEMBER_JOINED = 'member_joined', 'Member Joined'
    MEMBER_LEFT = 'member_left', 'Member Left'
    ADMIN_CHANGED = 'admin_changed', 'Admin Changed'
    SETTLEMENT_PAID = 'settlement_paid', 'Settlement Paid'


class NotificationStatus(models.TextChoices):
    UNREAD = 'unread', 'Unread'
    READ = 'read', 'Read'
    ACTIONED = 'actioned', 'Actioned'


class Notification(models.Model):
    """
    In-app notification center (V2 only, per spec Section 8). Actionable notifications
    (invite, admin_transfer) stay visibly pending until responded to, even once viewed —
    viewing only ever moves unread -> read, never -> actioned. Actioned status is set
    explicitly by the accept/decline/promote endpoints.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=32, choices=NotificationType.choices)
    actionable = models.BooleanField(default=False)
    status = models.CharField(max_length=16, choices=NotificationStatus.choices, default=NotificationStatus.UNREAD)
    title = models.CharField(max_length=150)
    body = models.CharField(max_length=500, blank=True)
    related_entity_id = models.IntegerField(null=True, blank=True)
    related_invite = models.ForeignKey(
        GroupInvite, on_delete=models.SET_NULL, null=True, blank=True, related_name='notifications'
    )
    related_admin_transfer = models.ForeignKey(
        AdminTransferRequest, on_delete=models.SET_NULL, null=True, blank=True, related_name='notifications'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', 'status'])]

    def __str__(self):
        return f"{self.type} for {self.user} ({self.status})"
