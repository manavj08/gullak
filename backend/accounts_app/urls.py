from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenBlacklistView
from . import views

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('login/refresh/', TokenRefreshView.as_view(), name='login_refresh'),
    path('logout/', TokenBlacklistView.as_view(), name='logout'),
    path('me/', views.MeView.as_view(), name='me'),
    path('username-lookup/', views.UsernameLookupView.as_view(), name='username_lookup'),
    path('mpin/set/', views.SetMpinView.as_view(), name='mpin_set'),
    path('mpin/verify/', views.VerifyMpinView.as_view(), name='mpin_verify'),
    path('password/change/', views.ChangePasswordView.as_view(), name='password_change'),
    path('password/reset/', views.PasswordResetRequestView.as_view(), name='password_reset'),
    path('password/reset/confirm/', views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
]
