from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import ExpenseEntry, ExpenseShare, Settlement, ExpenseSplitType

User = get_user_model()


class MiniUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username']


class ExpenseShareSerializer(serializers.ModelSerializer):
    user = MiniUserSerializer(read_only=True)

    class Meta:
        model = ExpenseShare
        fields = ['id', 'user', 'share_amount']


class ExpenseEntrySerializer(serializers.ModelSerializer):
    paid_by = MiniUserSerializer(read_only=True)
    created_by = MiniUserSerializer(read_only=True)
    shares = ExpenseShareSerializer(many=True, read_only=True)

    class Meta:
        model = ExpenseEntry
        fields = [
            'id', 'account', 'paid_by', 'created_by', 'description', 'amount',
            'category', 'split_type', 'expense_date', 'note', 'created_at', 'shares',
        ]
        read_only_fields = ['id', 'account', 'paid_by', 'created_by', 'created_at', 'shares']


class LogExpenseSerializer(serializers.Serializer):
    paid_by = serializers.IntegerField()
    description = serializers.CharField(max_length=200)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    category = serializers.ChoiceField(choices=ExpenseEntry._meta.get_field('category').choices)
    split_type = serializers.ChoiceField(choices=ExpenseSplitType.choices, default=ExpenseSplitType.EQUAL)
    expense_date = serializers.DateField()
    note = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    participant_ids = serializers.ListField(child=serializers.IntegerField(), min_length=1)
    exact_shares = serializers.DictField(
        child=serializers.DecimalField(max_digits=12, decimal_places=2), required=False,
    )

    def validate(self, data):
        if data['split_type'] == ExpenseSplitType.EXACT and not data.get('exact_shares'):
            raise serializers.ValidationError({'exact_shares': 'Required when split_type is "exact".'})
        return data


class SettlementSerializer(serializers.ModelSerializer):
    payer = MiniUserSerializer(read_only=True)
    payee = MiniUserSerializer(read_only=True)
    upi_link = serializers.ReadOnlyField()

    class Meta:
        model = Settlement
        fields = [
            'id', 'account', 'payer', 'payee', 'amount', 'status',
            'generated_at', 'paid_at', 'upi_link',
        ]
        read_only_fields = fields
