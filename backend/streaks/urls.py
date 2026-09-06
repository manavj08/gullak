from django.urls import path
from . import views

urlpatterns = [
    path('check-in/', views.CheckInView.as_view(), name='streak_checkin'),
    path('summary/', views.StreakSummaryView.as_view(), name='streak_summary'),
]
