import re
from urllib.parse import parse_qs, urlparse

from django.core import mail
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status

User = get_user_model()


def _extract_reset_params(email_body):
    """Pulls uid/token out of the reset link embedded in a sent email body."""
    match = re.search(r'(https?://\S+/reset-password\?\S+)', email_body)
    assert match, 'reset link not found in email body'
    query = parse_qs(urlparse(match.group(1)).query)
    return query['uid'][0], query['token'][0]


class RegistrationLoginTests(APITestCase):
    def test_register_and_login(self):
        resp = self.client.post(reverse('register'), {
            'username': 'alice', 'email': 'alice@example.com',
            'phone': '+919876543210', 'password': 'StrongPass123!',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)

        resp = self.client.post(reverse('login'), {
            'email': 'alice@example.com', 'password': 'StrongPass123!',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('access', resp.data)
        self.assertIn('refresh', resp.data)

    def test_login_wrong_password_rejected(self):
        User.objects.create_user(username='bob', email='bob@example.com', password='CorrectPass123!')
        resp = self.client.post(reverse('login'), {'email': 'bob@example.com', 'password': 'WrongPass'})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_password_never_stored_plaintext(self):
        user = User.objects.create_user(username='carol', email='carol@example.com', password='SecretPass123!')
        self.assertNotEqual(user.password, 'SecretPass123!')
        self.assertTrue(user.password.startswith('argon2$'))


class MpinTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='dave', email='dave@example.com', password='StrongPass123!')
        self.client.force_authenticate(self.user)

    def test_set_and_verify_mpin(self):
        resp = self.client.post(reverse('mpin_set'), {'mpin': '1234'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        resp = self.client.post(reverse('mpin_verify'), {'mpin': '1234'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_verify_wrong_mpin_rejected(self):
        self.client.post(reverse('mpin_set'), {'mpin': '1234'})
        resp = self.client.post(reverse('mpin_verify'), {'mpin': '9999'})
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_mpin_must_be_numeric_4_to_6_digits(self):
        resp = self.client.post(reverse('mpin_set'), {'mpin': 'abcd'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_verify_without_mpin_set(self):
        resp = self.client.post(reverse('mpin_verify'), {'mpin': '1234'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class PasswordResetTests(APITestCase):
    def setUp(self):
        # These tests call auth-throttled endpoints repeatedly; clear the
        # shared throttle cache so this class doesn't exhaust the 'auth'
        # scope's budget for whichever test class runs next.
        from django.core.cache import cache
        cache.clear()
        self.user = User.objects.create_user(username='erin', email='erin@example.com', password='OldPass123!')

    def tearDown(self):
        from django.core.cache import cache
        cache.clear()

    def test_reset_flow(self):
        resp = self.client.post(reverse('password_reset'), {'email': 'erin@example.com'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertNotIn('dev_uid', resp.data)
        self.assertNotIn('dev_token', resp.data)

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertEqual(sent.to, ['erin@example.com'])
        self.assertIn('Reset your Gullak password', sent.subject)
        self.assertTrue(any(ct == 'text/html' for _, ct in sent.alternatives))
        uid, token = _extract_reset_params(sent.body)

        resp = self.client.post(reverse('password_reset_confirm'), {
            'uid': uid, 'token': token, 'new_password': 'NewPass456!',
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        resp = self.client.post(reverse('login'), {'email': 'erin@example.com', 'password': 'NewPass456!'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_reset_does_not_reveal_unknown_email(self):
        resp = self.client.post(reverse('password_reset'), {'email': 'nobody@example.com'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertNotIn('dev_uid', resp.data)
        self.assertEqual(resp.data['detail'], 'If that email exists, a reset link has been sent.')
        self.assertEqual(len(mail.outbox), 0)  # no email sent for an address with no account

    def test_response_is_identical_whether_or_not_the_email_exists(self):
        known_resp = self.client.post(reverse('password_reset'), {'email': 'erin@example.com'})
        unknown_resp = self.client.post(reverse('password_reset'), {'email': 'nobody@example.com'})
        self.assertEqual(known_resp.data, unknown_resp.data)
        self.assertEqual(known_resp.status_code, unknown_resp.status_code)

    def test_reused_token_is_rejected(self):
        self.client.post(reverse('password_reset'), {'email': 'erin@example.com'})
        uid, token = _extract_reset_params(mail.outbox[0].body)
        self.client.post(reverse('password_reset_confirm'), {
            'uid': uid, 'token': token, 'new_password': 'NewPass456!',
        })
        # The token is single-use: Django's token generator bakes the
        # password hash into the hash it checks, so it's invalidated the
        # moment the password changes.
        resp = self.client.post(reverse('password_reset_confirm'), {
            'uid': uid, 'token': token, 'new_password': 'AnotherPass789!',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_token_is_rejected(self):
        resp = self.client.post(reverse('password_reset'), {'email': 'erin@example.com'})
        uid, _ = _extract_reset_params(mail.outbox[0].body)
        resp = self.client.post(reverse('password_reset_confirm'), {
            'uid': uid, 'token': 'not-a-real-token', 'new_password': 'NewPass456!',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_malformed_uid_is_rejected(self):
        resp = self.client.post(reverse('password_reset_confirm'), {
            'uid': 'not-valid-base64!!', 'token': 'whatever', 'new_password': 'NewPass456!',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reset_link_points_at_the_configured_frontend_url(self):
        from django.conf import settings
        self.client.post(reverse('password_reset'), {'email': 'erin@example.com'})
        uid, token = _extract_reset_params(mail.outbox[0].body)
        expected_prefix = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?uid="
        self.assertIn(expected_prefix, mail.outbox[0].body)

    def test_mail_send_failure_does_not_change_the_response(self):
        from unittest.mock import patch
        with patch('accounts_app.services.EmailMultiAlternatives.send', side_effect=Exception('SMTP down')):
            resp = self.client.post(reverse('password_reset'), {'email': 'erin@example.com'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['detail'], 'If that email exists, a reset link has been sent.')
