from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register('accounts', views.AccountViewSet, basename='account')
router.register('transactions', views.TransactionViewSet, basename='transaction')

urlpatterns = [
    path('transactions/create/', views.CreateTransactionView.as_view(), name='transaction_create'),
    path('transactions/transfer/', views.CreateTransferView.as_view(), name='transaction_transfer'),
    path('transactions/export/', views.TransactionExportView.as_view(), name='transaction_export'),
    path('gullak/', views.GullakSummaryView.as_view(), name='gullak_summary'),
    path('analytics/net-worth-history/', views.NetWorthHistoryView.as_view(), name='net_worth_history'),
    path('analytics/spend-by-category/', views.SpendByCategoryView.as_view(), name='spend_by_category'),
    path('', include(router.urls)),
]
