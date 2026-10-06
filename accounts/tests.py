from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class LoginRememberMeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='remember-user',
            password='test-pass-123',
            role='customer',
            is_approved=True,
        )
        self.login_url = reverse('accounts:login')
        self.session_cookie_name = settings.SESSION_COOKIE_NAME

    def test_login_without_remember_me_expires_at_browser_close(self):
        response = self.client.post(
            self.login_url,
            {
                'username': self.user.username,
                'password': 'test-pass-123',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('accounts:redirect_after_login'))
        self.assertTrue('_auth_user_id' in self.client.session)
        self.assertTrue(self.client.session.get_expire_at_browser_close())
        session_cookie = response.cookies[self.session_cookie_name]
        self.assertEqual(session_cookie.get('max-age'), '')
        self.assertEqual(session_cookie.get('expires'), '')

    def test_login_with_remember_me_uses_persistent_session(self):
        response = self.client.post(
            self.login_url,
            {
                'username': self.user.username,
                'password': 'test-pass-123',
                'remember_me': 'on',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('accounts:redirect_after_login'))
        self.assertTrue('_auth_user_id' in self.client.session)
        self.assertFalse(self.client.session.get_expire_at_browser_close())
        session_cookie = response.cookies[self.session_cookie_name]
        self.assertEqual(int(session_cookie['max-age']), settings.SESSION_COOKIE_AGE)
        self.assertTrue(session_cookie['expires'])