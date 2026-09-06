from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction as db_transaction
from django.utils import timezone

from .models import (
    SharedAccountMember, SharedAccountRole, GroupInvite, GroupInviteStatus,
    GroupOccasion, AdminTransferRequest, AdminTransferStatus,
    Notification, NotificationType, NotificationStatus, SharedContribution,
)

User = settings.AUTH_USER_MODEL


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

def _create_notification(*, user, type_, title, body='', actionable=False,
                          related_entity_id=None, related_invite=None, related_admin_transfer=None):
    return Notification.objects.create(
        user=user, type=type_, title=title, body=body, actionable=actionable,
        related_entity_id=related_entity_id, related_invite=related_invite,
        related_admin_transfer=related_admin_transfer,
    )


def notify_goal_deduction_applied(*, user, amount: Decimal, applied: list):
    """Informational notice after V2's automatic emergency-unblock deduction (goals/services.auto_apply_deduction)."""
    if not applied:
        body = f'An emergency unblock of ₹{amount} was covered by your unallocated Gullak funds — no goals were affected.'
    else:
        parts = '; '.join(f"{a['goal_name']} -₹{a['deducted']}" for a in applied)
        body = f'An emergency unblock reduced ₹{amount} from your goal-allocated funds, split automatically: {parts}.'
    _create_notification(
        user=user, type_=NotificationType.GOAL_UNDERFUNDED,
        title='Goal funds adjusted after emergency unblock', body=body, actionable=False,
    )


def list_notifications(user):
    return Notification.objects.filter(user=user)


def unread_count(user):
    return Notification.objects.filter(user=user, status=NotificationStatus.UNREAD).count()


@db_transaction.atomic
def mark_visible_as_read(user):
    """Opening the notification page marks visible (unread) items as read. Actionable
    items already sitting at 'unread' move to 'read' but stay visually pending in the UI
    until actually actioned — the UI, not this status, drives that distinction alongside
    `actionable`+`status != actioned`."""
    Notification.objects.filter(user=user, status=NotificationStatus.UNREAD).update(status=NotificationStatus.READ)


# ---------------------------------------------------------------------------
# Invites (Relationship pair + Family/Friends group) — username-based, accept-required
# ---------------------------------------------------------------------------

@db_transaction.atomic
def send_invite(*, inviter, invited_username: str, account):
    """
    Sends an invite to join `account` (a shared_pair or shared_group wallet.Account),
    looked up by username. Recipient must accept before membership is created.
    """
    from django.contrib.auth import get_user_model
    UserModel = get_user_model()

    if not account.is_shared:
        raise ValidationError({'account': 'Target account is not a shared account.'})
    if not SharedAccountMember.objects.filter(account=account, user=inviter).exists():
        raise ValidationError({'account': 'Only current members can invite others.'})

    try:
        invited_user = UserModel.objects.get(username=invited_username)
    except UserModel.DoesNotExist:
        raise ValidationError({'invited_username': 'No user found with that username.'})

    if invited_user.id == inviter.id:
        raise ValidationError({'invited_username': 'You cannot invite yourself.'})
    if SharedAccountMember.objects.filter(account=account, user=invited_user).exists():
        raise ValidationError({'invited_username': 'This user is already a member.'})
    if GroupInvite.objects.filter(account=account, invited_user=invited_user, status=GroupInviteStatus.PENDING).exists():
        raise ValidationError({'invited_username': 'This user already has a pending invite to this account.'})

    from wallet.models import AccountOwnerType
    if account.owner_type == AccountOwnerType.SHARED_PAIR:
        member_count = SharedAccountMember.objects.filter(account=account).count()
        pending_count = GroupInvite.objects.filter(account=account, status=GroupInviteStatus.PENDING).count()
        if member_count + pending_count >= 2:
            raise ValidationError({'account': 'A Relationship account can only have 2 people.'})

    invite = GroupInvite.objects.create(account=account, invited_by=inviter, invited_user=invited_user)
    _create_notification(
        user=invited_user, type_=NotificationType.INVITE,
        title=f'{inviter.username} invited you to "{account.name}"',
        body='Accept to join, or decline. No one can add you without your approval.',
        actionable=True, related_entity_id=account.id, related_invite=invite,
    )
    return invite


@db_transaction.atomic
def respond_to_invite(*, user, invite: GroupInvite, accept: bool):
    if invite.invited_user_id != user.id:
        raise ValidationError({'detail': 'This invite is not addressed to you.'})
    if invite.status != GroupInviteStatus.PENDING:
        raise ValidationError({'detail': 'This invite has already been responded to.'})

    invite.status = GroupInviteStatus.ACCEPTED if accept else GroupInviteStatus.DECLINED
    invite.responded_at = timezone.now()
    invite.save(update_fields=['status', 'responded_at'])

    Notification.objects.filter(related_invite=invite, user=user).update(status=NotificationStatus.ACTIONED)

    if accept:
        SharedAccountMember.objects.get_or_create(
            account=invite.account, user=user, defaults={'role': SharedAccountRole.MEMBER}
        )
        for member in SharedAccountMember.objects.filter(account=invite.account).exclude(user=user):
            _create_notification(
                user=member.user, type_=NotificationType.MEMBER_JOINED,
                title=f'{user.username} joined "{invite.account.name}"',
                actionable=False, related_entity_id=invite.account.id,
            )
    return invite


# ---------------------------------------------------------------------------
# Group membership / admin management
# ---------------------------------------------------------------------------

@db_transaction.atomic
def create_shared_pair_account(*, creator, name: str):
    from wallet.models import Account, AccountCategory, AccountOwnerType
    account = Account.objects.create(
        user=creator, name=name, category=AccountCategory.SAVINGS,
        owner_type=AccountOwnerType.SHARED_PAIR,
    )
    SharedAccountMember.objects.create(account=account, user=creator, role=SharedAccountRole.MEMBER)
    return account


@db_transaction.atomic
def create_shared_group_account(*, creator, name: str, occasion_name: str,
                                 occasion_date=None, reminder_enabled=False):
    from wallet.models import Account, AccountCategory, AccountOwnerType
    account = Account.objects.create(
        user=creator, name=name, category=AccountCategory.SAVINGS,
        owner_type=AccountOwnerType.SHARED_GROUP,
    )
    SharedAccountMember.objects.create(account=account, user=creator, role=SharedAccountRole.ADMIN)
    GroupOccasion.objects.create(
        account=account, name=occasion_name, occasion_date=occasion_date, reminder_enabled=reminder_enabled,
    )
    return account


def _require_admin(account, user):
    membership = SharedAccountMember.objects.filter(account=account, user=user).first()
    if not membership or membership.role != SharedAccountRole.ADMIN:
        raise ValidationError({'detail': 'Only the group admin can perform this action.'})
    return membership


@db_transaction.atomic
def remove_member(*, account, actor, target_user):
    """Admin removes a member (or a member leaves via a separate leave_account call).
    Per the confirmed decision, their already-contributed amount stays in the pool."""
    _require_admin(account, actor)
    membership = SharedAccountMember.objects.filter(account=account, user=target_user).first()
    if not membership:
        raise ValidationError({'detail': 'User is not a member of this account.'})
    if membership.role == SharedAccountRole.ADMIN:
        raise ValidationError({'detail': 'Cannot remove the admin. Transfer admin role first.'})
    membership.delete()
    for m in SharedAccountMember.objects.filter(account=account):
        _create_notification(
            user=m.user, type_=NotificationType.MEMBER_LEFT,
            title=f'{target_user.username} was removed from "{account.name}"',
            body='Their past contribution stays in the group\'s pooled total.',
            actionable=False, related_entity_id=account.id,
        )


@db_transaction.atomic
def leave_account(*, account, user):
    membership = SharedAccountMember.objects.filter(account=account, user=user).first()
    if not membership:
        raise ValidationError({'detail': 'You are not a member of this account.'})
    if membership.role == SharedAccountRole.ADMIN:
        other_members = SharedAccountMember.objects.filter(account=account).exclude(user=user)
        if other_members.exists():
            raise ValidationError({'detail': 'Transfer admin role to another member before leaving.'})
    membership.delete()
    for m in SharedAccountMember.objects.filter(account=account):
        _create_notification(
            user=m.user, type_=NotificationType.MEMBER_LEFT,
            title=f'{user.username} left "{account.name}"',
            body='Their past contribution stays in the group\'s pooled total.',
            actionable=False, related_entity_id=account.id,
        )


@db_transaction.atomic
def request_admin_transfer(*, account, actor, target_user):
    _require_admin(account, actor)
    if not SharedAccountMember.objects.filter(account=account, user=target_user).exists():
        raise ValidationError({'detail': 'Target user is not a member of this account.'})
    request_obj = AdminTransferRequest.objects.create(account=account, requested_by=actor, target_user=target_user)
    _create_notification(
        user=target_user, type_=NotificationType.ADMIN_TRANSFER,
        title=f'{actor.username} wants to make you admin of "{account.name}"',
        actionable=True, related_entity_id=account.id, related_admin_transfer=request_obj,
    )
    return request_obj


@db_transaction.atomic
def respond_to_admin_transfer(*, user, request_obj: AdminTransferRequest, accept: bool):
    if request_obj.target_user_id != user.id:
        raise ValidationError({'detail': 'This request is not addressed to you.'})
    if request_obj.status != AdminTransferStatus.PENDING:
        raise ValidationError({'detail': 'This request has already been responded to.'})

    request_obj.status = AdminTransferStatus.ACCEPTED if accept else AdminTransferStatus.DECLINED
    request_obj.responded_at = timezone.now()
    request_obj.save(update_fields=['status', 'responded_at'])
    Notification.objects.filter(related_admin_transfer=request_obj, user=user).update(status=NotificationStatus.ACTIONED)

    if accept:
        old_admin = SharedAccountMember.objects.filter(
            account=request_obj.account, role=SharedAccountRole.ADMIN
        ).first()
        new_admin = SharedAccountMember.objects.get(account=request_obj.account, user=user)
        new_admin.role = SharedAccountRole.ADMIN
        new_admin.save(update_fields=['role'])
        if old_admin and old_admin.user_id != user.id:
            old_admin.role = SharedAccountRole.MEMBER
            old_admin.save(update_fields=['role'])
        for m in SharedAccountMember.objects.filter(account=request_obj.account):
            _create_notification(
                user=m.user, type_=NotificationType.ADMIN_CHANGED,
                title=f'{user.username} is now the admin of "{request_obj.account.name}"',
                actionable=False, related_entity_id=request_obj.account.id,
            )
    return request_obj


# ---------------------------------------------------------------------------
# Visibility rule enforcement — aggregate-only for other members
# ---------------------------------------------------------------------------

def get_visible_contributions(*, account, requesting_user):
    """
    Server-side enforcement of the V2 visibility rule: the requesting member's own
    contribution is returned in full (itemized), every other member's is folded into
    a single 'others_aggregate' figure. This must be the ONLY way contribution data
    is ever serialized for a shared account — never a raw per-member list to the client.
    """
    contributions = SharedContribution.objects.filter(account=account)
    own = next((c.contributed_amount for c in contributions if c.user_id == requesting_user.id), Decimal('0.00'))
    others_aggregate = sum(
        (c.contributed_amount for c in contributions if c.user_id != requesting_user.id), Decimal('0.00')
    )
    return {'own_contribution': own, 'others_aggregate': others_aggregate}
