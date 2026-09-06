from django.urls import path
from . import views

urlpatterns = [
    path('groups/<int:account_id>/expenses/', views.GroupExpenseListView.as_view(), name='group_expense_list'),
    path('groups/<int:account_id>/expenses/<int:expense_id>/', views.ExpenseDetailView.as_view(), name='expense_detail'),
    path('groups/<int:account_id>/settlements/', views.SettlementListView.as_view(), name='settlement_list'),
    path('groups/<int:account_id>/settlements/generate/', views.GenerateSettlementsView.as_view(), name='settlement_generate'),
    path('groups/<int:account_id>/settlements/<int:settlement_id>/mark-paid/', views.MarkSettlementPaidView.as_view(), name='settlement_mark_paid'),
]
