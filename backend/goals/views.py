from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import viewsets, permissions, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import Goal, PendingGoalDeduction
from .serializers import (
    GoalSerializer, AddFundsSerializer, PendingGoalDeductionSerializer, ResolvePendingDeductionSerializer,
)


def _dvalidation_to_drf(exc: DjangoValidationError):
    if hasattr(exc, 'message_dict'):
        return exc.message_dict
    return {'detail': exc.messages if hasattr(exc, 'messages') else str(exc)}


class GoalViewSet(viewsets.ModelViewSet):
    serializer_class = GoalSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Goal.objects.filter(user=self.request.user)

    def perform_destroy(self, instance):
        services.delete_goal(user=self.request.user, goal=instance)

    @action(detail=True, methods=['post'], url_path='add-funds')
    def add_funds(self, request, pk=None):
        goal = self.get_object()
        serializer = AddFundsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            updated = services.add_funds_to_goal(
                user=request.user, goal=goal, add_amount=serializer.validated_data['add_amount'],
            )
        except DjangoValidationError as e:
            return Response(_dvalidation_to_drf(e), status=status.HTTP_400_BAD_REQUEST)
        return Response(GoalSerializer(updated).data)


class PendingGoalDeductionListView(generics.ListAPIView):
    """Unresolved emergency-unblock overages the user still needs to assign to a goal."""
    serializer_class = PendingGoalDeductionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return services.list_pending_deductions(self.request.user)


class ResolvePendingDeductionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk=None):
        try:
            deduction = PendingGoalDeduction.objects.get(pk=pk, user=request.user)
        except PendingGoalDeduction.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ResolvePendingDeductionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.resolve_pending_deduction(
                user=request.user, deduction=deduction,
                allocations=serializer.validated_data['allocations'],
            )
        except DjangoValidationError as e:
            return Response(_dvalidation_to_drf(e), status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': 'Deduction resolved.'})
