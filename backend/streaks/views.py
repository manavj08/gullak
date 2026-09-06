from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import DailyCheckIn
from .serializers import DailyCheckInSerializer, CheckInRequestSerializer, StreakSummarySerializer


class CheckInView(APIView):
    """Explicit manual check-in (e.g. 'no transactions today' button)."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CheckInRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        check_in = services.record_check_in(
            user=request.user, local_date=serializer.validated_data['date'], is_manual=True,
        )
        return Response(DailyCheckInSerializer(check_in).data, status=status.HTTP_200_OK)


class StreakSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        today_str = request.query_params.get('date')
        if not today_str:
            return Response({'date': 'Query param "date" (YYYY-MM-DD, local date) is required.'}, status=400)
        serializer = CheckInRequestSerializer(data={'date': today_str})
        serializer.is_valid(raise_exception=True)
        local_date = serializer.validated_data['date']

        current_streak = services.compute_current_streak(user=request.user, as_of_date=local_date)
        checked_in_today = DailyCheckIn.objects.filter(user=request.user, date=local_date).exists()
        return Response(StreakSummarySerializer({
            'current_streak': current_streak,
            'checked_in_today': checked_in_today,
        }).data)
