from unittest.mock import Mock, patch

from authlib.integrations.base_client import OAuthError
from django.contrib.auth import get_user_model
from django.http import HttpResponseRedirect
from django.test import TestCase, override_settings

from core.models import TelegramAccess


@override_settings(
    TELEGRAM_OIDC_CLIENT_ID="123456",
    TELEGRAM_OIDC_CLIENT_SECRET="secret",
    TELEGRAM_AUTH_BOOTSTRAP_IDS=set(),
)
class TelegramAuthTests(TestCase):
    def client_with_claims(self, **overrides):
        claims = {
            "id": 123456789,
            "sub": "123456789",
            "name": "Test Operator",
            "given_name": "Test",
            "family_name": "Operator",
        }
        claims.update(overrides)
        oidc = Mock()
        oidc.authorize_access_token.return_value = {"userinfo": claims}
        return oidc

    @override_settings(TELEGRAM_OIDC_CLIENT_ID="", TELEGRAM_OIDC_CLIENT_SECRET="")
    def test_telegram_start_reports_missing_configuration(self):
        response = self.client.get("/auth/telegram/")
        self.assertEqual(response.status_code, 503)

    @patch("core.auth_views._telegram_client")
    def test_login_starts_oidc_and_preserves_safe_next(self, get_client):
        oidc = get_client.return_value
        oidc.authorize_redirect.return_value = HttpResponseRedirect(
            "https://oauth.telegram.org/auth"
        )
        response = self.client.get("/auth/telegram/?next=/streaming/messages/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            self.client.session["telegram_login_next"], "/streaming/messages/"
        )
        callback = oidc.authorize_redirect.call_args.args[1]
        self.assertTrue(callback.endswith("/auth/callback/"))

    @patch("core.auth_views._telegram_client")
    def test_whitelisted_user_gets_local_staff_session(self, get_client):
        access = TelegramAccess.objects.create(telegram_id=123456789, label="Operator")
        get_client.return_value = self.client_with_claims()
        session = self.client.session
        session["telegram_login_next"] = "/core/settings/"
        session.save()

        response = self.client.get("/auth/callback/?code=valid")

        self.assertRedirects(response, "/core/settings/", fetch_redirect_response=False)
        user = get_user_model().objects.get(username="telegram:123456789")
        self.assertTrue(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.has_usable_password())
        self.assertEqual(access.__class__.objects.get(pk=access.pk).user, user)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    @patch("core.auth_views._telegram_client")
    def test_unknown_user_is_created_inactive_and_denied(self, get_client):
        get_client.return_value = self.client_with_claims(id=555, sub="555")
        response = self.client.get("/auth/callback/?code=valid")
        self.assertRedirects(
            response,
            "/auth/denied/?telegram_id=555",
            fetch_redirect_response=False,
        )
        self.assertFalse(get_user_model().objects.exists())
        access = TelegramAccess.objects.get(telegram_id=555)
        self.assertEqual(access.label, "Test Operator")
        self.assertFalse(access.is_active)
        self.assertFalse(access.is_admin)

    @patch("core.auth_views._telegram_client")
    def test_pending_login_does_not_create_duplicate_request(self, get_client):
        TelegramAccess.objects.create(telegram_id=555, is_active=False)
        get_client.return_value = self.client_with_claims(id=555, sub="555")

        self.client.get("/auth/callback/?code=valid")

        self.assertEqual(TelegramAccess.objects.filter(telegram_id=555).count(), 1)
        self.assertEqual(
            TelegramAccess.objects.get(telegram_id=555).label,
            "Test Operator",
        )

    @override_settings(TELEGRAM_AUTH_BOOTSTRAP_IDS={123456789})
    @patch("core.auth_views._telegram_client")
    def test_bootstrap_id_creates_admin_access(self, get_client):
        get_client.return_value = self.client_with_claims()
        response = self.client.get("/auth/callback/?code=valid")
        self.assertEqual(response.status_code, 302)
        access = TelegramAccess.objects.get(telegram_id=123456789)
        self.assertTrue(access.is_admin)
        self.assertTrue(access.user.is_superuser)

    @patch("core.auth_views._telegram_client")
    def test_invalid_oidc_response_is_rejected(self, get_client):
        get_client.return_value.authorize_access_token.side_effect = OAuthError(
            error="invalid_grant"
        )
        response = self.client.get("/auth/callback/?code=invalid")
        self.assertEqual(response.status_code, 400)

    def test_logout_requires_post(self):
        user = get_user_model().objects.create_user("local")
        self.client.force_login(user)
        self.assertEqual(self.client.get("/auth/logout/").status_code, 405)
        self.assertRedirects(
            self.client.post("/auth/logout/"),
            "/auth/login/",
            fetch_redirect_response=False,
        )
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_disabled_access_revokes_existing_session(self):
        user = get_user_model().objects.create_user("telegram:123456789", is_staff=True)
        TelegramAccess.objects.create(telegram_id=123456789, user=user, is_active=False)
        self.client.force_login(user)
        self.client.get("/")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_page_offers_both_authentication_methods(self):
        response = self.client.get("/auth/login/")
        self.assertContains(response, "Mit Django anmelden")
        self.assertContains(response, "Mit Telegram anmelden")

    def test_django_staff_user_can_login(self):
        user = get_user_model().objects.create_user(
            "operator", password="safe-test-password", is_staff=True
        )
        response = self.client.post(
            "/auth/login/",
            {
                "username": "operator",
                "password": "safe-test-password",
                "next": "/streaming/messages/",
            },
        )
        self.assertRedirects(
            response, "/streaming/messages/", fetch_redirect_response=False
        )
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_non_staff_django_user_is_denied(self):
        get_user_model().objects.create_user(
            "viewer", password="safe-test-password", is_staff=False
        )
        response = self.client.post(
            "/auth/login/",
            {"username": "viewer", "password": "safe-test-password"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "nicht für das Dashboard freigeschaltet")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_human_pages_require_login_but_operational_routes_do_not(self):
        response = self.client.get("/streaming/messages/?status=pending")
        self.assertRedirects(
            response,
            "/auth/login/?next=%2Fstreaming%2Fmessages%2F%3Fstatus%3Dpending",
            fetch_redirect_response=False,
        )
        self.assertEqual(self.client.get("/api/v1/health/").status_code, 200)
        self.assertEqual(self.client.get("/metrics/").status_code, 200)
