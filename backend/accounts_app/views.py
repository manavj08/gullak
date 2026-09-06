from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from . import services
from .serializers import (
    RegisterSerializer, UserSerializer, SetMpinSerializer, VerifyMpinSerializer,
    ChangePasswordSerializer, PasswordResetRequestSerializer, PasswordResetConfirmSerializer,
)

User = get_user_model()


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Login with email (USERNAME_FIELD) — default already uses it, kept explicit for clarity."""
    pass


class LoginView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer
    throttle_scope = 'auth'


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_scope = 'auth'


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class UsernameLookupView(APIView):
    """
    V2: checks whether a username exists, for the shared-account invite flow's
    'find by username' step. Deliberately returns only existence + username, never any
    other profile field, per the confirmed username-based (not phone/email) invite design.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        username = request.query_params.get('username', '').strip()
        if not username:
            return Response({'detail': 'username query parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)
        user = User.objects.filter(username=username).exclude(pk=request.user.pk).first()
        if not user:
            return Response({'found': False})
        return Response({'found': True, 'username': user.username})


class SetMpinView(APIView):
    """Set or update MPIN. Requires an authenticated (password-logged-in) session."""
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = 'mpin'

    def post(self, request):
        serializer = SetMpinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request.user.set_mpin(serializer.validated_data['mpin'])
        request.user.save(update_fields=['mpin_hash'])
        return Response({'detail': 'MPIN set successfully.'}, status=status.HTTP_200_OK)


class VerifyMpinView(APIView):
    """Quick-unlock: verifies MPIN for an already-authenticated (valid token) user."""
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = 'mpin'

    def post(self, request):
        if not request.user.has_mpin():
            return Response({'detail': 'MPIN not set for this account.'}, status=status.HTTP_400_BAD_REQUEST)
        serializer = VerifyMpinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if request.user.check_mpin(serializer.validated_data['mpin']):
            return Response({'detail': 'MPIN verified.'}, status=status.HTTP_200_OK)
        return Response({'detail': 'Incorrect MPIN.'}, status=status.HTTP_401_UNAUTHORIZED)


class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(serializer.validated_data['old_password']):
            return Response({'detail': 'Old password is incorrect.'}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        return Response({'detail': 'Password changed successfully.'})


class PasswordResetRequestView(APIView):
    """
    Sends a password-reset email containing a tokenized link to the
    frontend's /reset-password page. Uses whatever EMAIL_BACKEND is
    configured (SMTP if credentials are set, otherwise Django's console
    backend for local/demo use, which prints the email to the server log
    instead of actually sending it — see settings.py / README).

    Always returns the same generic response whether or not the email
    exists, and whether or not the send succeeded, so this endpoint can't be
    used to enumerate registered emails or probe for mail-server failures.
    """
    permission_classes = [permissions.AllowAny]
    throttle_scope = 'auth'

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        generic_response = Response({'detail': 'If that email exists, a reset link has been sent.'})

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return generic_response

        services.send_password_reset_email(user)
        return generic_response


class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = 'auth'

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            uid = force_str(urlsafe_base64_decode(data['uid']))
            user = User.objects.get(pk=uid)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            return Response({'detail': 'Invalid reset link.'}, status=status.HTTP_400_BAD_REQUEST)

        if not default_token_generator.check_token(user, data['token']):
            return Response({'detail': 'Invalid or expired reset link.'}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(data['new_password'])
        user.save()
        return Response({'detail': 'Password reset successfully.'})
