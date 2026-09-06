from decimal import Decimal

from rest_framework import serializers

from .models import (
    SharedAccountMember, GroupInvite, GroupOccasion, AdminTransferRequest, Notification,
)


class MemberUserSerializer(serializers.Serializer):
    """Minimal, non-sensitive user fields safe to expose to other group members."""
    id = serializers.IntegerField()
    username = serializers.CharField()


class SharedAccountMemberSerializer(serializers.ModelSerializer):
    user = MemberUserSerializer(read_only=True)

    class Meta:
        model = SharedAccountMember
        fields = ['id', 'user', 'role', 'joined_at']


class GroupOccasionSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupOccasion
        fields = ['name', 'occasion_date', 'reminder_enabled']


class CreateSharedPairSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)


class CreateSharedGroupSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    occasion_name = serializers.CharField(max_length=100)
    occasion_date = serializers.DateField(required=False, allow_null=True)
    reminder_enabled = serializers.BooleanField(required=False, default=False)


class SendInviteSerializer(serializers.Serializer):
    invited_username = serializers.CharField(max_length=150)


class GroupInviteSerializer(serializers.ModelSerializer):
    invited_by = MemberUserSerializer(read_only=True)
    invited_user = MemberUserSerializer(read_only=True)
    account_id = serializers.IntegerField(source='account.id', read_only=True)
    account_name = serializers.CharField(source='account.name', read_only=True)

    class Meta:
        model = GroupInvite
        fields = ['id', 'account_id', 'account_name', 'invited_by', 'invited_user', 'status', 'created_at', 'responded_at']


class RespondInviteSerializer(serializers.Serializer):
    accept = serializers.BooleanField()


class AdminTransferRequestSerializer(serializers.ModelSerializer):
    requested_by = MemberUserSerializer(read_only=True)
    target_user = MemberUserSerializer(read_only=True)

    class Meta:
        model = AdminTransferRequest
        fields = ['id', 'account', 'requested_by', 'target_user', 'status', 'created_at', 'responded_at']


class RequestAdminTransferSerializer(serializers.Serializer):
    target_username = serializers.CharField(max_length=150)


class RespondAdminTransferSerializer(serializers.Serializer):
    accept = serializers.BooleanField()


class RemoveMemberSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            'id', 'type', 'actionable', 'status', 'title', 'body',
            'related_entity_id', 'related_invite', 'related_admin_transfer', 'created_at',
        ]


class SharedAccountVisibilitySerializer(serializers.Serializer):
    """Server-enforced aggregate-only view — see social.services.get_visible_contributions."""
    own_contribution = serializers.DecimalField(max_digits=12, decimal_places=2)
    others_aggregate = serializers.DecimalField(max_digits=12, decimal_places=2)


class ContributeToSharedSerializer(serializers.Serializer):
    from_account = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    client_request_id = serializers.CharField(required=False, allow_blank=True, max_length=64)


class SharedEmergencyUnblockSerializer(serializers.Serializer):
    to_account = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    client_request_id = serializers.CharField(required=False, allow_blank=True, max_length=64)


class SplitSuggestionRequestSerializer(serializers.Serializer):
    new_amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    shared_account_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list,
        help_text="Optional: also include common goals funded from these shared accounts in the suggestion.",
    )


class SplitSuggestionItemSerializer(serializers.Serializer):
    goal_id = serializers.IntegerField()
    goal_name = serializers.CharField()
    suggested_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    funding_source = serializers.CharField()


class ApplySplitItemSerializer(serializers.Serializer):
    goal_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0'))


class ApplySplitSerializer(serializers.Serializer):
    allocations = ApplySplitItemSerializer(many=True)

    def validate_allocations(self, value):
        if not value:
            raise serializers.ValidationError("At least one allocation is required.")
        return value


class SharedGoalMemberProgressSerializer(serializers.Serializer):
    """Aggregate-only progress view for a common goal — mirrors SharedAccountVisibilitySerializer."""
    own_contribution = serializers.DecimalField(max_digits=12, decimal_places=2)
    others_aggregate = serializers.DecimalField(max_digits=12, decimal_places=2)
    target_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    allocated_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    remaining_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
