from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import GoalViewSet, PendingGoalDeductionListView, ResolvePendingDeductionView

router = DefaultRouter()
router.register('', GoalViewSet, basename='goal')

urlpatterns = [
    path('pending-deductions/', PendingGoalDeductionListView.as_view(), name='pending_deductions_list'),
    path('pending-deductions/<int:pk>/resolve/', ResolvePendingDeductionView.as_view(), name='pending_deduction_resolve'),
    path('', include(router.urls)),
]
