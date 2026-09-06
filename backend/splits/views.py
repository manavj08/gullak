from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import DecimalField, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import Settlement, SettlementStatus, SplitExpense, SplitGroup
from .permissions import user_is_group_member
from .serializers import (
    AddMemberSerializer, CreateSplitExpenseSerializer, CreateSplitGroupSerializer,
    SaveUpiIdSerializer, SettlementSerializer, SplitExpenseSerializer,
    SplitGroupDetailSerializer, SplitGroupSerializer, UpdateSplitGroupSerializer,
)

User = get_user_model()


def _validation_errors(exc: DjangoValidationError):
    return exc.message_dict if hasattr(exc, 'message_dict') else {'detail': str(exc)}


def _not_found():
    return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)


def _get_group_or_404(user, group_id):
    """Members-only group lookup. Non-members and non-existent groups both
    get a 404, so group existence isn't leaked to outsiders."""
    group = SplitGroup.objects.filter(pk=group_id).first()
    if not group or not user_is_group_member(group, user):
        return None, _not_found()
    return group, None


class SplitGroupListCreateView(APIView):
    """GET: groups the current user belongs to (with each group's pending settlement total).
    POST: create a group (creator becomes admin)."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Correlated subquery (not a second join) so it doesn't fan out against
        # the `members` join used to scope groups to the current user.
        pending_subquery = Settlement.objects.filter(
            group=OuterRef('pk'), status=SettlementStatus.PENDING,
        ).order_by().values('group').annotate(total=Sum('amount')).values('total')
        groups = SplitGroup.objects.filter(members__user=request.user).distinct().annotate(
            pending_settlement_total=Coalesce(
                Subquery(pending_subquery, output_field=DecimalField(max_digits=12, decimal_places=2)),
                Value(Decimal('0.00'), output_field=DecimalField(max_digits=12, decimal_places=2)),
            ),
        )
        return Response(SplitGroupSerializer(groups, many=True).data)

    def post(self, request):
        serializer = CreateSplitGroupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        group = services.create_group(
            name=d['name'], created_by=request.user,
            settlement_mode=d['settlement_mode'], member_ids=d.get('member_ids'),
        )
        return Response(SplitGroupDetailSerializer(group).data, status=status.HTTP_201_CREATED)


class SplitGroupDetailView(APIView):
    """GET: group details including members. PATCH: update settlement mode (creator only). Members only."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, group_id):
        group, error = _get_group_or_404(request.user, group_id)
        if error:
            return error
        group = SplitGroup.objects.prefetch_related('members__user').get(pk=group.pk)
        return Response(SplitGroupDetailSerializer(group).data)

    def patch(self, request, group_id):
        group, error = _get_group_or_404(request.user, group_id)
        if error:
            return error
        serializer = UpdateSplitGroupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.update_settlement_mode(
                group=group, settlement_mode=serializer.validated_data['settlement_mode'],
                requesting_user=request.user,
            )
        except DjangoValidationError as exc:
            return Response(_validation_errors(exc), status=status.HTTP_400_BAD_REQUEST)
        group = SplitGroup.objects.prefetch_related('members__user').get(pk=group.pk)
        return Response(SplitGroupDetailSerializer(group).data)


class UserLookupView(APIView):
    """GET ?username=... -> {found, id, username}. Used by the frontend to resolve a
    username into a user_id before adding them to a split group. Unlike
    accounts_app's invite-flow lookup (which deliberately hides the id, since that
    flow requires the invitee to accept), this app adds members directly with no
    acceptance step, so the id must be exposed here for the add-member call to work."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        username = request.query_params.get('username', '').strip()
        if not username:
            return Response({'detail': 'username query parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)
        user = User.objects.filter(username=username).exclude(pk=request.user.pk).first()
        if not user:
            return Response({'found': False})
        return Response({'found': True, 'id': user.id, 'username': user.username})


class GroupMemberListView(APIView):
    """POST: add a member. Only current members can add."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, group_id):
        group, error = _get_group_or_404(request.user, group_id)
        if error:
            return error
        serializer = AddMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.add_member(group=group, user_id=serializer.validated_data['user_id'], requesting_user=request.user)
        except DjangoValidationError as exc:
            return Response(_validation_errors(exc), status=status.HTTP_400_BAD_REQUEST)
        group = SplitGroup.objects.prefetch_related('members__user').get(pk=group.pk)
        return Response(SplitGroupDetailSerializer(group).data, status=status.HTTP_201_CREATED)


class GroupMemberDetailView(APIView):
    """DELETE: remove a member. Creator can remove anyone; a member can remove only themselves."""
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, group_id, user_id):
        group, error = _get_group_or_404(request.user, group_id)
        if error:
            return error
        try:
            services.remove_member(group=group, user_id=user_id, requesting_user=request.user)
        except DjangoValidationError as exc:
            return Response(_validation_errors(exc), status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)


class GroupExpenseListCreateView(APIView):
    """GET: a group's expenses. POST: log a new expense. Members only."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, group_id):
        group, error = _get_group_or_404(request.user, group_id)
        if error:
            return error
        expenses = SplitExpense.objects.filter(group=group).select_related(
            'paid_by', 'created_by',
        ).prefetch_related('shares__user')
        return Response(SplitExpenseSerializer(expenses, many=True).data)

    def post(self, request, group_id):
        group, error = _get_group_or_404(request.user, group_id)
        if error:
            return error
        serializer = CreateSplitExpenseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        try:
            expense = services.create_expense(
                group=group, created_by=request.user, paid_by_id=d['paid_by'],
                description=d['description'], amount=d['amount'], split_type=d['split_type'],
                expense_date=d['expense_date'], note=d.get('note', ''),
                participant_ids=d['participant_ids'], exact_shares=d.get('exact_shares'),
                percentages=d.get('percentages'),
            )
        except DjangoValidationError as exc:
            return Response(_validation_errors(exc), status=status.HTTP_400_BAD_REQUEST)
        expense = SplitExpense.objects.prefetch_related('shares__user').get(pk=expense.pk)
        return Response(SplitExpenseSerializer(expense).data, status=status.HTTP_201_CREATED)


class ExpenseDetailView(APIView):
    """DELETE: remove an expense. Only the payer or the person who logged it."""
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, group_id, expense_id):
        group, error = _get_group_or_404(request.user, group_id)
        if error:
            return error
        expense = SplitExpense.objects.filter(pk=expense_id, group=group).first()
        if not expense:
            return _not_found()
        try:
            services.delete_expense(expense=expense, requesting_user=request.user)
        except DjangoValidationError as exc:
            return Response(_validation_errors(exc), status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SettlementListView(APIView):
    """GET: current settlements (pending + paid history) for a group. Members only."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, group_id):
        group, error = _get_group_or_404(request.user, group_id)
        if error:
            return error
        settlements = Settlement.objects.filter(group=group).select_related('payer', 'payee')
        return Response(SettlementSerializer(settlements, many=True).data)


class RecalculateSettlementsView(APIView):
    """POST: (re)generate settlements from current expense balances. Any member may trigger this."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, group_id):
        group, error = _get_group_or_404(request.user, group_id)
        if error:
            return error
        settlements = services.generate_settlements(group=group)
        return Response(SettlementSerializer(settlements, many=True).data, status=status.HTTP_201_CREATED)


class MarkSettlementPaidView(APIView):
    """POST: the payee confirms they received the money."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, group_id, settlement_id):
        group, error = _get_group_or_404(request.user, group_id)
        if error:
            return error
        settlement = Settlement.objects.filter(pk=settlement_id, group=group).first()
        if not settlement:
            return _not_found()
        try:
            settlement = services.mark_settlement_paid(settlement=settlement, requesting_user=request.user)
        except DjangoValidationError as exc:
            return Response(_validation_errors(exc), status=status.HTTP_400_BAD_REQUEST)
        return Response(SettlementSerializer(settlement).data)


class SettlementPaymentInfoView(APIView):
    """GET: UPI payment info (link + fields) so the payer can pay the payee."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, group_id, settlement_id):
        group, error = _get_group_or_404(request.user, group_id)
        if error:
            return error
        settlement = Settlement.objects.filter(pk=settlement_id, group=group).select_related('payee', 'group').first()
        if not settlement:
            return _not_found()
        return Response(services.payment_info(settlement=settlement))


class SettlementCalculationView(APIView):
    """GET: explains why a settlement's amount is what it is — the
    "Show Calculation" feature. Points to the specific contributing
    expenses (pairwise groups) or the full group ledger + each person's
    overall net (global groups). See services.settlement.explain_settlement."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, group_id, settlement_id):
        group, error = _get_group_or_404(request.user, group_id)
        if error:
            return error
        settlement = Settlement.objects.filter(pk=settlement_id, group=group).select_related(
            'payer', 'payee', 'group',
        ).first()
        if not settlement:
            return _not_found()
        return Response(services.explain_settlement(settlement))


class SaveUpiIdView(APIView):
    """POST: save/validate the current user's UPI ID, used to build settlement pay links."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = SaveUpiIdSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.save_upi_id(user=request.user, upi_id=serializer.validated_data['upi_id'])
        except DjangoValidationError as exc:
            return Response(_validation_errors(exc), status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': 'UPI ID saved.', 'upi_id': request.user.upi_id})
