from django.test import TestCase, override_settings

from core.factories import SettingsFactory


class DashboardAccessTest(TestCase):
    def test_anonymous_users_cannot_change_dashboard_or_view_settings(self):
        assert self.client.post("/", {"action": "approve"}).status_code == 302
        assert self.client.get("/core/settings/").status_code == 302

    def test_operational_endpoints_are_public(self):
        assert self.client.get("/api/v1/readiness/").status_code == 200
        metrics = self.client.get("/metrics/")
        assert metrics.status_code == 200
        assert b"paws_messages" in metrics.content

    @override_settings(SECURE_SSL_REDIRECT=True)
    def test_operational_endpoints_are_exempt_from_https_redirect(self):
        assert self.client.get("/api/v1/health/").status_code == 200
        assert self.client.get("/api/v1/readiness/").status_code == 200
        assert self.client.get("/metrics/").status_code == 200

    @override_settings(SECURE_SSL_REDIRECT=True)
    def test_other_endpoints_still_redirect_to_https(self):
        response = self.client.get("/api/v1/settings/1/")

        assert response.status_code == 301
        assert response["Location"] == "https://testserver/api/v1/settings/1/"


@override_settings(
    API_AUTH_TOKEN="admin-token",
    BOT_API_AUTH_TOKEN="bot-token",
    DISPLAY_API_AUTH_TOKEN="display-token",
)
class ApiRoleTest(TestCase):
    def test_display_token_only_sees_display_settings(self):
        SettingsFactory(
            reg_api_key="secret",
            event_api_url="https://sigma.example/events?signature=secret",
        )
        response = self.client.get(
            "/api/v1/settings/1/", HTTP_X_API_TOKEN="display-token"
        )
        assert response.status_code == 200
        assert "reg_api_key" not in response.json()
        assert "event_api_url" not in response.json()
        denied = self.client.post(
            "/api/v1/message/", {}, HTTP_X_API_TOKEN="display-token"
        )
        assert denied.status_code == 403

    def test_bot_token_cannot_change_settings(self):
        response = self.client.patch(
            "/api/v1/settings/1/",
            {"bot_status": "offline"},
            content_type="application/json",
            HTTP_X_API_TOKEN="bot-token",
        )
        assert response.status_code == 403

    def test_display_token_can_fetch_central_theme(self):
        response = self.client.get(
            "/api/v1/themes/default/",
            HTTP_X_API_TOKEN="display-token",
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["schema_version"] == 2
        assert payload["name"] == "default"

    def test_default_theme_does_not_expose_assets(self):
        response = self.client.get(
            "/api/v1/themes/default/legacy/assets/chat_bottom/",
            HTTP_X_API_TOKEN="display-token",
        )
        assert response.status_code == 404

    def test_bot_token_cannot_fetch_theme_assets(self):
        response = self.client.get(
            "/api/v1/themes/default/legacy/assets/chat_top/",
            HTTP_X_API_TOKEN="bot-token",
        )
        assert response.status_code == 403

    def test_unknown_central_theme_is_not_found(self):
        response = self.client.get(
            "/api/v1/themes/not-there/",
            HTTP_X_API_TOKEN="display-token",
        )
        assert response.status_code == 404
