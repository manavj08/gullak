import csv

from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from django.utils import timezone as dj_timezone

from . import services
from .models import Account, Transaction, TransactionType, AccountCategory
from .serializers import (
    AccountSerializer, TransactionSerializer, BlockUnblockSerializer,
    CreateTransactionSerializer, CreateTransferSerializer, MarkSettledSerializer,
)
from streaks.services import record_check_in

GULLAK_LEG_TYPES = [TransactionType.GULLAK_BLOCK, TransactionType.GULLAK_UNBLOCK]


def _dvalidation_to_drf(exc: DjangoValidationError):
    if hasattr(exc, 'message_dict'):
        return exc.message_dict
    return {'detail': exc.messages if hasattr(exc, 'messages') else str(exc)}


class AccountViewSet(viewsets.ModelViewSet):
    serializer_class = AccountSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['category', 'is_archived']
    ordering_fields = ['created_at', 'name']

    def get_queryset(self):
        return Account.objects.filter(user=self.request.user)

    def perform_destroy(self, instance):
        if instance.category == AccountCategory.GULLAK:
            raise DjangoValidationError({'detail': 'The Gullak account cannot be deleted.'})
        instance.is_archived = True
        instance.save(update_fields=['is_archived', 'updated_at'])

    @action(detail=True, methods=['post'])
    def block(self, request, pk=None):
        account = self.get_object()
        serializer = BlockUnblockSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.block_funds(
                user=request.user, account=account,
                amount=serializer.validated_data['amount'],
                client_request_id=serializer.validated_data.get('client_request_id') or None,
            )
        except DjangoValidationError as e:
            return Response(_dvalidation_to_drf(e), status=status.HTTP_400_BAD_REQUEST)
        account.refresh_from_db()
        return Response(AccountSerializer(account).data)

    @action(detail=True, methods=['post'], url_path='emergency-unblock')
    def emergency_unblock(self, request, pk=None):
        account = self.get_object()
        serializer = BlockUnblockSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.emergency_unblock_funds(
                user=request.user, account=account,
                amount=serializer.validated_data['amount'],
                client_request_id=serializer.validated_data.get('client_request_id') or None,
            )
        except DjangoValidationError as e:
            return Response(_dvalidation_to_drf(e), status=status.HTTP_400_BAD_REQUEST)
        account.refresh_from_db()
        return Response(AccountSerializer(account).data)


class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read/list transactions. Creation goes through dedicated endpoints below (business-rule enforcement).

    By default, excludes Gullak block/unblock legs — those only appear on the
    Gullak account's own detail page (pass ?include_gullak=true to include them,
    used internally by the Gullak account page).
    """
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['account', 'type', 'category', 'settled']
    ordering_fields = ['timestamp', 'amount']

    def get_queryset(self):
        qs = Transaction.objects.filter(user=self.request.user)
        include_gullak = self.request.query_params.get('include_gullak', 'false').lower() == 'true'
        if not include_gullak:
            qs = qs.exclude(type__in=GULLAK_LEG_TYPES)
        return qs

    @action(detail=True, methods=['patch'], url_path='settle')
    def settle(self, request, pk=None):
        txn = self.get_object()
        if txn.type not in ('lend', 'borrow'):
            return Response({'detail': 'Only lend/borrow transactions can be settled.'}, status=400)
        serializer = MarkSettledSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        txn.settled = serializer.validated_data['settled']
        txn.save(update_fields=['settled'])
        return Response(TransactionSerializer(txn).data)


class TransactionExportView(APIView):
    """
    GET -> downloads a CSV of the requesting user's transactions.

    Honors the same filters as the transactions list (?type=, ?account=,
    ?category=, ?settled=, ?include_gullak=) so exporting matches whatever
    the person is currently looking at on the Transactions page. Columns:
    Date, Type, Category, Amount, Account, Description.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = Transaction.objects.filter(user=request.user).select_related('account').order_by('-timestamp')

        include_gullak = request.query_params.get('include_gullak', 'false').lower() == 'true'
        if not include_gullak:
            qs = qs.exclude(type__in=GULLAK_LEG_TYPES)

        for field in ('account', 'type', 'category', 'settled'):
            value = request.query_params.get(field)
            if value:
                qs = qs.filter(**{field: value})

        response = HttpResponse(content_type='text/csv')
        filename = f"gullak_transactions_{dj_timezone.localdate().isoformat()}.csv"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        writer.writerow(['Date', 'Type', 'Category', 'Amount', 'Account', 'Description'])
        for txn in qs.iterator():
            writer.writerow([
                dj_timezone.localtime(txn.timestamp).date().isoformat(),
                txn.get_type_display(),
                txn.get_category_display(),
                txn.amount,
                txn.account.name,
                txn.note,
            ])
        return response


class CreateTransactionView(APIView):
    """income / expense / lend / borrow — NOT transfer (see CreateTransferView), NOT Gullak (see block/unblock)."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CreateTransactionSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            txn = services.create_transaction(
                user=request.user,
                account=data['account'],
                type_=data['type'],
                amount=data['amount'],
                category=data.get('category') or None,
                note=data.get('note', ''),
                client_request_id=data.get('client_request_id') or None,
            )
        except DjangoValidationError as e:
            return Response(_dvalidation_to_drf(e), status=status.HTTP_400_BAD_REQUEST)
        record_check_in(user=request.user, local_date=dj_timezone.localdate(), had_transaction=True)
        return Response(TransactionSerializer(txn).data, status=status.HTTP_201_CREATED)


class CreateTransferView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CreateTransferSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            txn = services.create_transfer(
                user=request.user,
                from_account=data['from_account'],
                to_account=data['to_account'],
                amount=data['amount'],
                note=data.get('note', ''),
                client_request_id=data.get('client_request_id') or None,
            )
        except DjangoValidationError as e:
            return Response(_dvalidation_to_drf(e), status=status.HTTP_400_BAD_REQUEST)
        record_check_in(user=request.user, local_date=dj_timezone.localdate(), had_transaction=True)
        return Response(TransactionSerializer(txn).data, status=status.HTTP_201_CREATED)


class GullakSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from goals.services import total_allocated
        gullak_total = services.compute_gullak_total(request.user)
        allocated = total_allocated(request.user)
        gullak_account = services.get_or_create_gullak(request.user)
        return Response({
            'gullak_account_id': gullak_account.id,
            'gullak_total': gullak_total,
            'allocated': allocated,
            'unallocated': gullak_total - allocated,
            'net_worth': services.compute_net_worth(request.user),
        })


def _parse_days(request, default=30, minimum=1, maximum=365):
    try:
        days = int(request.query_params.get('days', default))
    except (TypeError, ValueError):
        days = default
    return max(minimum, min(days, maximum))


class NetWorthHistoryView(APIView):
    """GET ?days=30 (default) -> [{date, net_worth}, ...], oldest first.
    See services.net_worth_history for the reconstruction rule and its
    documented approximation for Revenue Generation / Loan-Debt accounts."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        days = _parse_days(request)
        return Response(services.net_worth_history(request.user, days=days))


class SpendByCategoryView(APIView):
    """GET ?days=30 (default) -> [{category, amount}, ...] for EXPENSE
    transactions in the period, largest first."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        days = _parse_days(request)
        return Response(services.spend_by_category(request.user, days=days))
