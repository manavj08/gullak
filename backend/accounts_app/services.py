"""Business logic kept out of views, matching the convention used across the
rest of this project (see e.g. wallet/services.py)."""
import logging

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

logger = logging.getLogger(__name__)


def build_password_reset_link(user) -> str:
    """The reset link points at the frontend SPA's /reset-password route
    (not a Django view) — see ResetPasswordPage.jsx, which reads uid/token
    from the query string and calls back into the confirm API."""
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?uid={uid}&token={token}"


def send_password_reset_email(user) -> bool:
    """
    Sends the password-reset email using whatever EMAIL_BACKEND is
    configured (SMTP if credentials are set, otherwise Django's console
    backend for local/demo use — see settings.py). Returns True if the send
    call succeeded, False if it raised (logged, not re-raised, so a mail
    server hiccup can't be used to probe which emails have accounts).
    """
    reset_link = build_password_reset_link(user)
    expiry_hours = max(1, settings.PASSWORD_RESET_TIMEOUT // 3600)
    context = {
        'display_name': user.get_full_name() or user.username,
        'email': user.email,
        'reset_link': reset_link,
        'expiry_hours': expiry_hours,
    }
    text_body = render_to_string('accounts_app/emails/password_reset_email.txt', context)
    html_body = render_to_string('accounts_app/emails/password_reset_email.html', context)

    try:
        message = EmailMultiAlternatives(
            subject='Reset your Gullak password',
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        message.attach_alternative(html_body, 'text/html')
        message.send(fail_silently=False)
        return True
    except Exception:
        logger.exception('Failed to send password reset email to user id=%s', user.pk)
        return False
