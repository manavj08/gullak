from decimal import Decimal
from rest_framework import serializers
from .models import Goal, PendingGoalDeduction


class GoalSerializer(serializers.ModelSerializer):
    progress_percent = serializers.ReadOnlyField()
    funding_source = serializers.ReadOnlyField()
    is_common_goal = serializers.ReadOnlyField()

    class Meta:
        model = Goal
        fields = [
            'id', 'name', 'item_link', 'target_amount', 'deadline',
            'allocated_amount', 'status', 'is_achieved', 'progress_percent',
            'funding_source', 'is_common_goal', 'funding_shared_account_id',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'allocated_amount', 'status', 'is_achieved', 'created_at', 'updated_at']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        shared_account_id = validated_data.get('funding_shared_account_id')
        if shared_account_id:
            from social.models import SharedAccountMember
            is_member = SharedAccountMember.objects.filter(
                account_id=shared_account_id, user=self.context['request'].user
            ).exists()
            if not is_member:
                raise serializers.ValidationError({
                    'funding_shared_account_id': 'You are not a member of this shared account.'
                })
        return super().create(validated_data)


    def update(self, instance, validated_data):
        # funding_shared_account_id is set once at creation and never changed afterward —
        # switching a goal's funding source after the fact would break the contribution
        # history already tracked against it (GoalContribution).
        validated_data.pop('funding_shared_account_id', None)
        return super().update(instance, validated_data)


class AddFundsSerializer(serializers.Serializer):
    add_amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'), help_text="Rupees")


class PendingGoalDeductionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PendingGoalDeduction
        fields = ['id', 'amount', 'created_at']


class ResolveAllocationItemSerializer(serializers.Serializer):
    goal_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0'))


class ResolvePendingDeductionSerializer(serializers.Serializer):
    allocations = ResolveAllocationItemSerializer(many=True)

    def validate_allocations(self, value):
        if not value:
            raise serializers.ValidationError("At least one allocation is required.")
        return value
