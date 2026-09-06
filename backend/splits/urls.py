from django.urls import path

from . import views

app_name = 'splits'

urlpatterns = [
    path('groups/', views.SplitGroupListCreateView.as_view(), name='group_list_create'),
    path('groups/<int:group_id>/', views.SplitGroupDetailView.as_view(), name='group_detail'),
    path('groups/<int:group_id>/members/', views.GroupMemberListView.as_view(), name='member_add'),
    path('groups/<int:group_id>/members/<int:user_id>/', views.GroupMemberDetailView.as_view(), name='member_remove'),
    path('groups/<int:group_id>/expenses/', views.GroupExpenseListCreateView.as_view(), name='expense_list_create'),
    path('groups/<int:group_id>/expenses/<int:expense_id>/', views.ExpenseDetailView.as_view(), name='expense_detail'),
    path('groups/<int:group_id>/settlements/', views.SettlementListView.as_view(), name='settlement_list'),
    path(
        'groups/<int:group_id>/settlements/recalculate/',
        views.RecalculateSettlementsView.as_view(), name='settlement_recalculate',
    ),
    path(
        'groups/<int:group_id>/settlements/<int:settlement_id>/mark-paid/',
        views.MarkSettlementPaidView.as_view(), name='settlement_mark_paid',
    ),
    path(
        'groups/<int:group_id>/settlements/<int:settlement_id>/payment-info/',
        views.SettlementPaymentInfoView.as_view(), name='settlement_payment_info',
    ),
    path(
        'groups/<int:group_id>/settlements/<int:settlement_id>/calculation/',
        views.SettlementCalculationView.as_view(), name='settlement_calculation',
    ),
    path('upi/save/', views.SaveUpiIdView.as_view(), name='upi_save'),
    path('users/lookup/', views.UserLookupView.as_view(), name='user_lookup'),
]
