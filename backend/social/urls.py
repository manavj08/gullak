from django.urls import path
from . import views

urlpatterns = [
    # Shared accounts
    path('shared-accounts/', views.SharedAccountListView.as_view(), name='shared_account_list'),
    path('shared-accounts/pair/', views.CreateSharedPairView.as_view(), name='shared_pair_create'),
    path('shared-accounts/group/', views.CreateSharedGroupView.as_view(), name='shared_group_create'),
    path('shared-accounts/<int:account_id>/', views.SharedAccountDetailView.as_view(), name='shared_account_detail'),
    path('shared-accounts/<int:account_id>/contribute/', views.ContributeToSharedAccountView.as_view(), name='shared_account_contribute'),
    path('shared-accounts/<int:account_id>/emergency-unblock/', views.SharedEmergencyUnblockView.as_view(), name='shared_account_unblock'),
    path('shared-accounts/<int:account_id>/invite/', views.SendInviteView.as_view(), name='shared_account_invite'),
    path('shared-accounts/<int:account_id>/leave/', views.LeaveSharedAccountView.as_view(), name='shared_account_leave'),
    path('shared-accounts/<int:account_id>/remove-member/', views.RemoveMemberView.as_view(), name='shared_account_remove_member'),
    path('shared-accounts/<int:account_id>/request-admin-transfer/', views.RequestAdminTransferView.as_view(), name='shared_account_request_admin_transfer'),

    # Invites (received)
    path('invites/', views.MyInvitesView.as_view(), name='my_invites'),
    path('invites/<int:invite_id>/respond/', views.RespondInviteView.as_view(), name='invite_respond'),

    # Admin transfer (received)
    path('admin-transfers/<int:request_id>/respond/', views.RespondAdminTransferView.as_view(), name='admin_transfer_respond'),

    # Notifications
    path('notifications/', views.NotificationListView.as_view(), name='notification_list'),
    path('notifications/unread-count/', views.NotificationUnreadCountView.as_view(), name='notification_unread_count'),

    # Smart Gullak-split suggestion
    path('split-suggestion/', views.SplitSuggestionView.as_view(), name='split_suggestion'),
    path('split-suggestion/apply/', views.ApplySplitSuggestionView.as_view(), name='split_suggestion_apply'),
    path('split-suggestion/my-shared-accounts/', views.MySharedAccountsForSplitView.as_view(), name='split_suggestion_my_shared_accounts'),

    # Common (shared-account-funded) goal detail
    path('goals/<int:goal_id>/', views.SharedGoalDetailView.as_view(), name='shared_goal_detail'),
]
