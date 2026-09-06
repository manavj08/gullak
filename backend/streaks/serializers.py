from rest_framework import serializers
from .models import DailyCheckIn


class DailyCheckInSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyCheckIn
        fields = ['id', 'date', 'had_transaction', 'is_manual_checkin', 'created_at']
        read_only_fields = ['id', 'created_at']


class CheckInRequestSerializer(serializers.Serializer):
    date = serializers.DateField(help_text="User's local calendar date (YYYY-MM-DD)")


class StreakSummarySerializer(serializers.Serializer):
    current_streak = serializers.IntegerField()
    checked_in_today = serializers.BooleanField()
