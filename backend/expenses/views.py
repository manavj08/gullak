from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from wallet.models import Account, AccountOwnerType
from social.models import SharedAccountMember
from . import services
from .models import ExpenseEntry, Settlement
from .serializers import (
    ExpenseEntrySerializer, LogExpenseSerializer, SettlementSerializer,
)


def _dvalidation_to_drf(exc: DjangoValidationError):
    if hasattr(exc, 'message_dict'):
        return exc.message_dict
    return {'detail': exc.messages if hasattr(exc, 'messages') else str(exc)}


def _get_group_account_or_404(user, account_id):
    """Same gate as social._get_member_account_or_404, restricted to shared_group accounts
    (expense splitting is not offered for shared_pair accounts)."""
    account = Account.objects.filter(pk=account_id).first()
    if not account or account.owner_type != AccountOwnerType.SHARED_GROUP:
        return None, Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    if not SharedAccountMember.objects.filter(account=account, user=user).exists():
        return None, Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    return account, None


class GroupExpenseListView(APIView):
    """GET: list expenses for a group. POST: log a new expense."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, account_id):
        account, error = _get_group_account_or_404(request.user, account_id)
        if error:
            return error
        entries = ExpenseEntry.objects.filter(account=account).select_related(
            'paid_by', 'created_by'
        ).prefetch_related('shares__user')
        return Response(ExpenseEntrySerializer(entries, many=True).data)

    def post(self, request, account_id):
        account, error = _get_group_account_or_404(request.user, account_id)
        if error:
            return error
        serializer = LogExpenseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        try:
            entry = services.log_expense(
                account=account, created_by=request.user, paid_by_id=d['paid_by'],
                description=d['description'], amount=d['amount'], category=d['category'],
                split_type=d['split_type'], expense_date=d['expense_date'], note=d.get('note', ''),
                participant_ids=d['participant_ids'], exact_shares=d.get('exact_shares'),
            )
        except DjangoValidationError as exc:
            return Response(_dvalidation_to_drf(exc), status=status.HTTP_400_BAD_REQUEST)
        entry.refresh_from_db()
        return Response(ExpenseEntrySerializer(entry).data, status=status.HTTP_201_CREATED)


class ExpenseDetailView(APIView):
    """DELETE: remove an expense (only by the payer or whoever logged it)."""
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, account_id, expense_id):
        account, error = _get_group_account_or_404(request.user, account_id)
        if error:
            return error
        entry = ExpenseEntry.objects.filter(pk=expense_id, account=account).first()
        if not entry:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            services.delete_expense(expense=entry, requesting_user=request.user)
        except DjangoValidationError as exc:
            return Response(_dvalidation_to_drf(exc), status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SettlementListView(APIView):
    """GET: current settlements (pending + paid) for a group."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, account_id):
        account, error = _get_group_account_or_404(request.user, account_id)
        if error:
            return error
        settlements = Settlement.objects.filter(account=account).select_related('payer', 'payee')
        return Response(SettlementSerializer(settlements, many=True).data)


class GenerateSettlementsView(APIView):
    """POST: recompute settlements from current expense balances. Any member may trigger this."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, account_id):
        account, error = _get_group_account_or_404(request.user, account_id)
        if error:
            return error
        settlements = services.generate_settlements(account=account)
        return Response(SettlementSerializer(settlements, many=True).data, status=status.HTTP_201_CREATED)


class MarkSettlementPaidView(APIView):
    """POST: the payee confirms they received the money."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, account_id, settlement_id):
        account, error = _get_group_account_or_404(request.user, account_id)
        if error:
            return error
        settlement = Settlement.objects.filter(pk=settlement_id, account=account).first()
        if not settlement:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            settlement = services.mark_settlement_paid(settlement=settlement, requesting_user=request.user)
        except DjangoValidationError as exc:
            return Response(_dvalidation_to_drf(exc), status=status.HTTP_400_BAD_REQUEST)
        return Response(SettlementSerializer(settlement).data)
