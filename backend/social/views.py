from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import permissions, status, generics
from rest_framework.response import Response
from rest_framework.views import APIView

from wallet.models import Account
from . import services
from .models import SharedAccountMember, GroupInvite, AdminTransferRequest, Notification
from .serializers import (
    CreateSharedPairSerializer, CreateSharedGroupSerializer, SendInviteSerializer,
    GroupInviteSerializer, RespondInviteSerializer, SharedAccountMemberSerializer,
    RequestAdminTransferSerializer, RespondAdminTransferSerializer, AdminTransferRequestSerializer,
    RemoveMemberSerializer, NotificationSerializer, SharedAccountVisibilitySerializer,
    ContributeToSharedSerializer, SharedEmergencyUnblockSerializer,
    SplitSuggestionRequestSerializer, SplitSuggestionItemSerializer, ApplySplitSerializer,
    SharedGoalMemberProgressSerializer,
)

User = get_user_model()


def _dvalidation_to_drf(exc: DjangoValidationError):
    if hasattr(exc, 'message_dict'):
        return exc.message_dict
    return {'detail': exc.messages if hasattr(exc, 'messages') else str(exc)}


def _get_member_account_or_404(user, account_id):
    """Fetches a shared account the requesting user is a member of, or raises 404-equivalent.
    This is the server-side gate that prevents any non-member from reading shared-account data."""
    account = Account.objects.filter(pk=account_id).first()
    if not account or not account.is_shared:
        return None, Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    if not SharedAccountMember.objects.filter(account=account, user=user).exists():
        # Deliberately 404, not 403 — don't reveal a shared account's existence to non-members.
        return None, Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    return account, None


class CreateSharedPairView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CreateSharedPairSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = services.create_shared_pair_account(creator=request.user, name=serializer.validated_data['name'])
        from wallet.serializers import AccountSerializer
        return Response(AccountSerializer(account).data, status=status.HTTP_201_CREATED)


class CreateSharedGroupView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CreateSharedGroupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        account = services.create_shared_group_account(
            creator=request.user, name=d['name'], occasion_name=d['occasion_name'],
            occasion_date=d.get('occasion_date'), reminder_enabled=d.get('reminder_enabled', False),
        )
        from wallet.serializers import AccountSerializer
        return Response(AccountSerializer(account).data, status=status.HTTP_201_CREATED)


class SharedAccountListView(APIView):
    """List shared accounts (pair + group) the requesting user is a member of."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from wallet.serializers import AccountSerializer
        account_ids = SharedAccountMember.objects.filter(user=request.user).values_list('account_id', flat=True)
        accounts = Account.objects.filter(id__in=account_ids, is_archived=False)
        return Response(AccountSerializer(accounts, many=True).data)


class SharedAccountDetailView(APIView):
    """Detail view for one shared account: members, occasion (if group), and the caller's
    aggregate-only visibility view — never a per-member itemized list."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, account_id):
        account, error = _get_member_account_or_404(request.user, account_id)
        if error:
            return error
        from wallet.serializers import AccountSerializer
        from goals.models import Goal
        members = SharedAccountMember.objects.filter(account=account).select_related('user')
        visibility = services.get_visible_contributions(account=account, requesting_user=request.user)
        common_goals = Goal.objects.filter(funding_shared_account_id=account.id)
        data = {
            'account': AccountSerializer(account).data,
            'members': SharedAccountMemberSerializer(members, many=True).data,
            'visibility': SharedAccountVisibilitySerializer(visibility).data,
            'common_goals': [
                {
                    'id': g.id, 'name': g.name, 'target_amount': g.target_amount,
                    'allocated_amount': g.allocated_amount, 'is_achieved': g.is_achieved,
                }
                for g in common_goals
            ],
        }
        if hasattr(account, 'occasion'):
            from .serializers import GroupOccasionSerializer
            data['occasion'] = GroupOccasionSerializer(account.occasion).data
        return Response(data)


class ContributeToSharedAccountView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, account_id):
        account, error = _get_member_account_or_404(request.user, account_id)
        if error:
            return error
        serializer = ContributeToSharedSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        from_account = Account.objects.filter(pk=d['from_account'], user=request.user).first()
        if not from_account:
            return Response({'from_account': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        from wallet.services import contribute_to_shared_account
        try:
            contribute_to_shared_account(
                user=request.user, from_account=from_account, shared_account=account,
                amount=d['amount'], client_request_id=d.get('client_request_id') or None,
            )
        except DjangoValidationError as e:
            return Response(_dvalidation_to_drf(e), status=status.HTTP_400_BAD_REQUEST)
        account.refresh_from_db()
        from wallet.serializers import AccountSerializer
        return Response(AccountSerializer(account).data)


class SharedEmergencyUnblockView(APIView):
    """Unblock only the requesting member's own contributed portion — enforced server-side
    in wallet.services.emergency_unblock_own_share, not just hidden in the UI."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, account_id):
        account, error = _get_member_account_or_404(request.user, account_id)
        if error:
            return error
        serializer = SharedEmergencyUnblockSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        to_account = Account.objects.filter(pk=d['to_account'], user=request.user).first()
        if not to_account:
            return Response({'to_account': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        from wallet.services import emergency_unblock_own_share
        try:
            emergency_unblock_own_share(
                user=request.user, shared_account=account, to_account=to_account,
                amount=d['amount'], client_request_id=d.get('client_request_id') or None,
            )
        except DjangoValidationError as e:
            return Response(_dvalidation_to_drf(e), status=status.HTTP_400_BAD_REQUEST)
        account.refresh_from_db()
        from wallet.serializers import AccountSerializer
        return Response(AccountSerializer(account).data)


class SendInviteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, account_id):
        account, error = _get_member_account_or_404(request.user, account_id)
        if error:
            return error
        serializer = SendInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            invite = services.send_invite(
                inviter=request.user, invited_username=serializer.validated_data['invited_username'], account=account,
            )
        except DjangoValidationError as e:
            return Response(_dvalidation_to_drf(e), status=status.HTTP_400_BAD_REQUEST)
        return Response(GroupInviteSerializer(invite).data, status=status.HTTP_201_CREATED)


class MyInvitesView(generics.ListAPIView):
    """Invites the requesting user has received (any status; UI filters to pending for the actionable badge)."""
    serializer_class = GroupInviteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return GroupInvite.objects.filter(invited_user=self.request.user)


class RespondInviteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, invite_id):
        invite = GroupInvite.objects.filter(pk=invite_id).first()
        if not invite:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = RespondInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            invite = services.respond_to_invite(user=request.user, invite=invite, accept=serializer.validated_data['accept'])
        except DjangoValidationError as e:
            return Response(_dvalidation_to_drf(e), status=status.HTTP_400_BAD_REQUEST)
        return Response(GroupInviteSerializer(invite).data)


class RemoveMemberView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, account_id):
        account, error = _get_member_account_or_404(request.user, account_id)
        if error:
            return error
        serializer = RemoveMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target = User.objects.filter(username=serializer.validated_data['username']).first()
        if not target:
            return Response({'username': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            services.remove_member(account=account, actor=request.user, target_user=target)
        except DjangoValidationError as e:
            return Response(_dvalidation_to_drf(e), status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': 'Member removed.'})


class LeaveSharedAccountView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, account_id):
        account, error = _get_member_account_or_404(request.user, account_id)
        if error:
            return error
        try:
            services.leave_account(account=account, user=request.user)
        except DjangoValidationError as e:
            return Response(_dvalidation_to_drf(e), status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': 'You left the account.'})


class RequestAdminTransferView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, account_id):
        account, error = _get_member_account_or_404(request.user, account_id)
        if error:
            return error
        serializer = RequestAdminTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target = User.objects.filter(username=serializer.validated_data['target_username']).first()
        if not target:
            return Response({'target_username': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            req = services.request_admin_transfer(account=account, actor=request.user, target_user=target)
        except DjangoValidationError as e:
            return Response(_dvalidation_to_drf(e), status=status.HTTP_400_BAD_REQUEST)
        return Response(AdminTransferRequestSerializer(req).data, status=status.HTTP_201_CREATED)


class RespondAdminTransferView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, request_id):
        req = AdminTransferRequest.objects.filter(pk=request_id).first()
        if not req:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = RespondAdminTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            req = services.respond_to_admin_transfer(user=request.user, request_obj=req, accept=serializer.validated_data['accept'])
        except DjangoValidationError as e:
            return Response(_dvalidation_to_drf(e), status=status.HTTP_400_BAD_REQUEST)
        return Response(AdminTransferRequestSerializer(req).data)


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return services.list_notifications(self.request.user)

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        # Opening the notification page marks visible items as read (V2 spec Section 8).
        services.mark_visible_as_read(request.user)
        return response


class NotificationUnreadCountView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({'unread_count': services.unread_count(request.user)})


class SplitSuggestionView(APIView):
    """
    V2: smart Gullak-split suggestion. Suggestion only — returned to the client for
    review/override; nothing is applied until ApplySplitSuggestionView is explicitly
    called. `new_amount` is capped server-side against live unallocated funds (personal
    Gullak, and separately each requested shared account's own unallocated pool).
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from goals.services import compute_urgency_split
        serializer = SplitSuggestionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        # Only include shared accounts the requester is actually a member of — a user
        # can't probe another shared account's goals by guessing its id.
        requested_ids = d.get('shared_account_ids') or []
        valid_ids = list(
            SharedAccountMember.objects.filter(account_id__in=requested_ids, user=request.user)
            .values_list('account_id', flat=True)
        )
        suggestion = compute_urgency_split(request.user, d['new_amount'], shared_account_ids=valid_ids)
        return Response(SplitSuggestionItemSerializer(suggestion, many=True).data)


class MySharedAccountsForSplitView(APIView):
    """Lightweight list (id + name) of the requester's shared accounts, for the
    'also split through a shared account?' picker step in the split-suggestion flow."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        account_ids = SharedAccountMember.objects.filter(user=request.user).values_list('account_id', flat=True)
        accounts = Account.objects.filter(id__in=account_ids, is_archived=False)
        return Response([{'id': a.id, 'name': a.name} for a in accounts])


class ApplySplitSuggestionView(APIView):
    """Applies a (possibly user-overridden) split across goals via the normal add_funds_to_goal
    path. For common goals, verifies the requester is actually a member of the funding shared
    account before crediting the contribution under their name."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from goals.models import Goal
        from goals.services import add_funds_to_goal
        serializer = ApplySplitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        results = []
        try:
            for alloc in serializer.validated_data['allocations']:
                if alloc['amount'] <= 0:
                    continue
                goal = Goal.objects.filter(pk=alloc['goal_id']).first()
                if not goal:
                    return Response({'detail': 'One or more goals were not found.'}, status=status.HTTP_404_NOT_FOUND)

                if goal.is_common_goal:
                    is_member = SharedAccountMember.objects.filter(
                        account_id=goal.funding_shared_account_id, user=request.user
                    ).exists()
                    if not is_member:
                        return Response(
                            {'detail': 'You are not a member of the shared account funding this goal.'},
                            status=status.HTTP_403_FORBIDDEN,
                        )
                    updated = add_funds_to_goal(
                        user=goal.user, goal=goal, add_amount=alloc['amount'], contributor=request.user,
                    )
                else:
                    if goal.user_id != request.user.id:
                        return Response({'detail': 'One or more goals were not found.'}, status=status.HTTP_404_NOT_FOUND)
                    updated = add_funds_to_goal(user=request.user, goal=goal, add_amount=alloc['amount'])

                results.append({'goal_id': updated.id, 'allocated_amount': updated.allocated_amount})
        except DjangoValidationError as e:
            return Response(_dvalidation_to_drf(e), status=status.HTTP_400_BAD_REQUEST)
        return Response({'applied': results})


class SharedGoalDetailView(APIView):
    """
    A common goal's detail view for shared/group accounts: target, allocated, remaining,
    and the requester's own-vs-combined-others progress — same aggregate-only visibility
    rule as the shared account's pool. Only accessible to members of the funding account.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, goal_id):
        from goals.models import Goal
        from goals.services import get_visible_goal_contributions
        goal = Goal.objects.filter(pk=goal_id, funding_shared_account_id__isnull=False).first()
        if not goal:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        is_member = SharedAccountMember.objects.filter(
            account_id=goal.funding_shared_account_id, user=request.user
        ).exists()
        if not is_member:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        visibility = get_visible_goal_contributions(goal=goal, requesting_user=request.user)
        data = {
            **visibility,
            'target_amount': goal.target_amount,
            'allocated_amount': goal.allocated_amount,
            'remaining_amount': max(goal.target_amount - goal.allocated_amount, Decimal('0.00')),
        }
        members = SharedAccountMember.objects.filter(
            account_id=goal.funding_shared_account_id
        ).select_related('user')
        return Response({
            'goal': {'id': goal.id, 'name': goal.name, 'deadline': goal.deadline, 'is_achieved': goal.is_achieved},
            'shared_account_id': goal.funding_shared_account_id,
            'progress': SharedGoalMemberProgressSerializer(data).data,
            'member_count': members.count(),
        })
