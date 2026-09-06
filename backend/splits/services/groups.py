"""Group membership management for the splits app."""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction as db_transaction

from ..models import SettlementMode, SplitGroup, SplitGroupMember, SplitGroupMemberRole

User = get_user_model()


@db_transaction.atomic
def create_group(*, name, created_by, settlement_mode=SettlementMode.GLOBAL, member_ids=None):
    group = SplitGroup.objects.create(name=name, created_by=created_by, settlement_mode=settlement_mode)
    SplitGroupMember.objects.create(group=group, user=created_by, role=SplitGroupMemberRole.ADMIN)
    for uid in set(member_ids or []):
        if uid != created_by.id:
            SplitGroupMember.objects.get_or_create(
                group=group, user_id=uid, defaults={'role': SplitGroupMemberRole.MEMBER},
            )
    return group


def is_member(group, user_id):
    return SplitGroupMember.objects.filter(group=group, user_id=user_id).exists()


def member_ids(group):
    return set(SplitGroupMember.objects.filter(group=group).values_list('user_id', flat=True))


def add_member(*, group, user_id, requesting_user):
    if not is_member(group, requesting_user.id):
        raise ValidationError({'detail': 'Only group members can add members.'})
    if not User.objects.filter(pk=user_id).exists():
        raise ValidationError({'user_id': 'No such user.'})
    if SplitGroupMember.objects.filter(group=group, user_id=user_id).exists():
        raise ValidationError({'user_id': 'This user is already a member of the group.'})
    return SplitGroupMember.objects.create(group=group, user_id=user_id, role=SplitGroupMemberRole.MEMBER)


def remove_member(*, group, user_id, requesting_user):
    """The group creator can remove anyone; any other member may remove only themselves (leave)."""
    membership = SplitGroupMember.objects.filter(group=group, user_id=user_id).first()
    if not membership:
        raise ValidationError({'detail': 'This user is not a member of the group.'})
    is_self = requesting_user.id == user_id
    is_creator = requesting_user.id == group.created_by_id
    if not (is_self or is_creator):
        raise ValidationError({'detail': 'Only the group creator can remove other members.'})
    if user_id == group.created_by_id:
        raise ValidationError({'detail': 'The group creator cannot be removed from the group.'})
    membership.delete()


def update_settlement_mode(*, group, settlement_mode, requesting_user):
    """Only the group creator may change how settlements are calculated."""
    if requesting_user.id != group.created_by_id:
        raise ValidationError({'detail': 'Only the group creator can change the settlement mode.'})
    group.settlement_mode = settlement_mode
    group.save(update_fields=['settlement_mode', 'updated_at'])
    return group
