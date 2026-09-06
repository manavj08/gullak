from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import (
    Settlement, SettlementMode, SplitExpense, SplitExpenseShare, SplitGroup,
    SplitGroupMember, SplitType,
)

User = get_user_model()


class MemberUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name']


class SplitGroupMemberSerializer(serializers.ModelSerializer):
    user = MemberUserSerializer(read_only=True)

    class Meta:
        model = SplitGroupMember
        fields = ['id', 'user', 'role', 'joined_at']


class SplitGroupSerializer(serializers.ModelSerializer):
    member_count = serializers.IntegerField(source='members.count', read_only=True)
    pending_settlement_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = SplitGroup
        fields = [
            'id', 'name', 'created_by', 'settlement_mode', 'member_count',
            'pending_settlement_total', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_by']


class SplitGroupDetailSerializer(serializers.ModelSerializer):
    members = SplitGroupMemberSerializer(many=True, read_only=True)

    class Meta:
        model = SplitGroup
        fields = ['id', 'name', 'created_by', 'settlement_mode', 'members', 'created_at', 'updated_at']


class CreateSplitGroupSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    settlement_mode = serializers.ChoiceField(choices=SettlementMode.choices, default=SettlementMode.GLOBAL)
    member_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)


class UpdateSplitGroupSerializer(serializers.Serializer):
    settlement_mode = serializers.ChoiceField(choices=SettlementMode.choices)


class AddMemberSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()


class SplitExpenseShareSerializer(serializers.ModelSerializer):
    user = MemberUserSerializer(read_only=True)

    class Meta:
        model = SplitExpenseShare
        fields = ['id', 'user', 'share_amount', 'percentage']


class SplitExpenseSerializer(serializers.ModelSerializer):
    paid_by = MemberUserSerializer(read_only=True)
    created_by = MemberUserSerializer(read_only=True)
    shares = SplitExpenseShareSerializer(many=True, read_only=True)

    class Meta:
        model = SplitExpense
        fields = [
            'id', 'group', 'description', 'amount', 'paid_by', 'created_by',
            'split_type', 'expense_date', 'note', 'shares', 'created_at',
        ]


class CreateSplitExpenseSerializer(serializers.Serializer):
    description = serializers.CharField(max_length=200)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    paid_by = serializers.IntegerField()
    split_type = serializers.ChoiceField(choices=SplitType.choices, default=SplitType.EQUAL)
    expense_date = serializers.DateField()
    note = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    participant_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)
    exact_shares = serializers.DictField(
        child=serializers.DecimalField(max_digits=12, decimal_places=2), required=False,
    )
    percentages = serializers.DictField(
        child=serializers.DecimalField(max_digits=5, decimal_places=2), required=False,
    )


class SettlementSerializer(serializers.ModelSerializer):
    payer = MemberUserSerializer(read_only=True)
    payee = MemberUserSerializer(read_only=True)

    class Meta:
        model = Settlement
        fields = ['id', 'group', 'payer', 'payee', 'amount', 'status', 'generated_at', 'paid_at', 'marked_paid_by']


class SaveUpiIdSerializer(serializers.Serializer):
    upi_id = serializers.CharField(max_length=100)
