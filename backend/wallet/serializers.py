from decimal import Decimal
from rest_framework import serializers
from .models import Account, Transaction, AccountCategory, BLOCK_CAPABLE_CATEGORIES


class AccountSerializer(serializers.ModelSerializer):
    net_worth_contribution = serializers.ReadOnlyField()
    is_block_capable = serializers.ReadOnlyField()
    is_gullak = serializers.ReadOnlyField()

    class Meta:
        model = Account
        fields = [
            'id', 'name', 'category', 'account_type', 'owner_type',
            'unblock_balance', 'block_balance',
            'principal', 'current_value', 'maturity_date',
            'credit_limit', 'amount_used', 'amount_owed', 'due_date',
            'is_archived', 'is_block_capable', 'is_gullak', 'net_worth_contribution',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        category = attrs.get('category', getattr(self.instance, 'category', None))
        if category == AccountCategory.GULLAK:
            raise serializers.ValidationError({
                'category': 'The Gullak account is created automatically and cannot be added manually.'
            })
        if category in BLOCK_CAPABLE_CATEGORIES:
            for f in ('principal', 'current_value', 'credit_limit', 'amount_used', 'amount_owed'):
                attrs.setdefault(f, None)
        elif category == AccountCategory.REVENUE_GENERATION:
            if attrs.get('principal') is None and getattr(self.instance, 'principal', None) is None:
                raise serializers.ValidationError({'principal': 'Required for Revenue Generation accounts.'})
            if attrs.get('current_value') is None and getattr(self.instance, 'current_value', None) is None:
                raise serializers.ValidationError({'current_value': 'Required for Revenue Generation accounts.'})
        elif category == AccountCategory.LOAN_DEBT:
            if attrs.get('amount_owed') is None and getattr(self.instance, 'amount_owed', None) is None:
                raise serializers.ValidationError({'amount_owed': 'Required for Loan/Debt accounts.'})
        return attrs

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class BlockUnblockSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'), help_text="Amount in rupees")
    client_request_id = serializers.CharField(required=False, allow_blank=True, max_length=64)


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = [
            'id', 'account', 'type', 'amount', 'category', 'note',
            'settled', 'transfer_pair', 'client_request_id', 'timestamp',
        ]
        read_only_fields = ['id', 'transfer_pair', 'timestamp']


class CreateTransactionSerializer(serializers.Serializer):
    account = serializers.PrimaryKeyRelatedField(queryset=Account.objects.all())
    type = serializers.ChoiceField(choices=['income', 'expense', 'lend', 'borrow'])
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    category = serializers.CharField(required=False, allow_blank=True)
    note = serializers.CharField(required=False, allow_blank=True, max_length=255)
    client_request_id = serializers.CharField(required=False, allow_blank=True, max_length=64)

    def validate_account(self, account):
        request = self.context['request']
        if account.user_id != request.user.id:
            raise serializers.ValidationError("Account does not belong to this user.")
        if account.category == AccountCategory.GULLAK:
            raise serializers.ValidationError("Cannot record a direct transaction on the Gullak account.")
        return account


class CreateTransferSerializer(serializers.Serializer):
    from_account = serializers.PrimaryKeyRelatedField(queryset=Account.objects.all())
    to_account = serializers.PrimaryKeyRelatedField(queryset=Account.objects.all())
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    note = serializers.CharField(required=False, allow_blank=True, max_length=255)
    client_request_id = serializers.CharField(required=False, allow_blank=True, max_length=64)

    def validate(self, attrs):
        request = self.context['request']
        for key in ('from_account', 'to_account'):
            if attrs[key].user_id != request.user.id:
                raise serializers.ValidationError({key: "Account does not belong to this user."})
            if attrs[key].category == AccountCategory.GULLAK:
                raise serializers.ValidationError({key: "Use block/emergency-unblock to move funds with Gullak."})
        if attrs['from_account'].pk == attrs['to_account'].pk:
            raise serializers.ValidationError("Cannot transfer to the same account.")
        return attrs


class MarkSettledSerializer(serializers.Serializer):
    settled = serializers.BooleanField()
