from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from streaming.factories import EventFactory, MediaAssetFactory, TextMessageFactory

from core.factories import SettingsFactory
from core.models import DisplayLog, WebDisplayAccess
from core.monitor_views import COOKIE_NAME, _encode_cursor


class WebDisplayAccessModelTest(TestCase):
    def test_rotation_stores_digest_not_plain_token(self):
        access = WebDisplayAccess.get_access()
        token = access.rotate()
        access.refresh_from_db()
        assert access.is_active
        assert access.accepts(token)
        assert token not in access.token_digest

    def test_revoke_invalidates_token(self):
        access = WebDisplayAccess.get_access()
        token = access.rotate()
        access.revoke()
        assert not access.accepts(token)


class WebDisplayManagementTest(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user("staff", is_staff=True)
        self.admin = get_user_model().objects.create_user(
            "admin", is_staff=True, is_superuser=True
        )

    def test_staff_sees_navbar_button_and_opens_monitor(self):
        self.client.force_login(self.staff)
        dashboard = self.client.get("/")
        assert dashboard.status_code == 200
        self.assertContains(dashboard, 'href="/monitor/"')
        assert 'target="_blank"' not in dashboard.content.decode()
        assert self.client.get("/monitor/").status_code == 200
        assert self.client.get("/monitor/feed/").status_code == 200

    def test_staff_cannot_manage_public_link(self):
        self.client.force_login(self.staff)
        assert self.client.get("/core/web-display/").status_code == 403
        assert (
            self.client.post("/core/web-display/", {"action": "rotate"}).status_code
            == 403
        )

    def test_admin_can_generate_and_revoke_public_link(self):
        self.client.force_login(self.admin)
        generated = self.client.post("/core/web-display/", {"action": "rotate"})
        assert generated.status_code == 200
        self.assertContains(generated, "/monitor/#")
        assert WebDisplayAccess.get_access().is_active

        revoked = self.client.post("/core/web-display/", {"action": "revoke"})
        assert revoked.status_code == 200
        assert not WebDisplayAccess.get_access().is_active


class PublicWebDisplayTest(TestCase):
    def setUp(self):
        SettingsFactory(
            display_mode="chat",
            display_duration_sec=8,
            scroll_speed_px=3,
            overlay_font_size=24,
            overlay_theme="default",
        )
        self.access = WebDisplayAccess.get_access()
        self.token = self.access.rotate()

    def _authorize(self):
        response = self.client.post(
            reverse("web_display_access"),
            {"token": self.token},
            content_type="application/json",
        )
        assert response.status_code == 200
        assert COOKIE_NAME in response.cookies
        return response

    def test_anonymous_feed_requires_monitor_cookie(self):
        page = self.client.get("/monitor/")
        assert page.status_code == 200
        assert page["Cache-Control"] == "no-store"
        assert "default-src 'self'" in page["Content-Security-Policy"]
        assert self.client.get("/monitor/feed/").status_code == 401
        response = self._authorize()
        assert self.token not in response.cookies[COOKIE_NAME].value
        assert self.client.get("/monitor/feed/").status_code == 200

    def test_wrong_token_is_rejected(self):
        response = self.client.post(
            reverse("web_display_access"),
            {"token": "wrong"},
            content_type="application/json",
        )
        assert response.status_code == 403

    def test_rotation_invalidates_existing_cookie(self):
        self._authorize()
        assert self.client.get("/monitor/feed/").status_code == 200
        self.access.rotate()
        assert self.client.get("/monitor/feed/").status_code == 401

    def test_initial_feed_returns_only_latest_approved_message(self):
        now = timezone.now()
        older = TextMessageFactory(
            status="approved", approved_at=now - timedelta(minutes=2)
        )
        latest = TextMessageFactory(
            status="approved", approved_at=now - timedelta(minutes=1)
        )
        TextMessageFactory(status="pending", approved_at=None)
        TextMessageFactory(status="rejected", approved_at=None)
        self._authorize()

        payload = self.client.get("/monitor/feed/").json()

        assert [item["id"] for item in payload["messages"]] == [str(latest.id)]
        assert str(older.id) not in {item["id"] for item in payload["messages"]}
        assert payload["settings"]["display_mode"] == "chat"
        assert payload["settings"]["overlay_theme"] == "default"
        assert payload["theme"]["schema_version"] == 2
        assert payload["theme"]["name"] == "default"
        assert payload["theme"]["chat"]["styles"]["message"]["color"] == "#111827"
        assert payload["theme"]["chat"]["background"]["color"] == "#f8fafc"

    def test_default_theme_exposes_crawling_configuration(self):
        self._authorize()

        payload = self.client.get("/monitor/feed/").json()

        assert payload["theme"]["ticker"]["width"] == -64
        assert payload["theme"]["ticker"]["scale"] == 1.0
        assert payload["theme"]["ticker"]["background"]["border_color"] == "#38bdf8"

    def test_feed_applies_event_display_overrides_when_messages_are_disabled(self):
        now = timezone.now()
        EventFactory(
            is_active=True,
            allow_messages=False,
            starts_at=now - timedelta(hours=1),
            ends_at=now + timedelta(hours=1),
            display_mode="crawling",
            scroll_speed_px=9,
        )
        self._authorize()

        payload = self.client.get("/monitor/feed/").json()

        assert payload["settings"]["display_mode"] == "crawling"
        assert payload["settings"]["scroll_speed_px"] == 9

    def test_monitor_theme_assets_are_unavailable_for_default_theme(self):
        url = "/monitor/themes/default/legacy/assets/chat_top/"
        assert self.client.get(url).status_code == 401
        self._authorize()

        response = self.client.get(url)

        assert response.status_code == 404

    def test_follow_up_feed_returns_new_approvals_without_side_effects(self):
        self._authorize()
        first = self.client.get("/monitor/feed/").json()
        message = TextMessageFactory(status="approved", approved_at=timezone.now())

        payload = self.client.get("/monitor/feed/", {"cursor": first["cursor"]}).json()

        assert [item["id"] for item in payload["messages"]] == [str(message.id)]
        message.refresh_from_db()
        assert message.displayed_at is None
        assert DisplayLog.objects.count() == 0

    def test_cursor_paginates_equal_timestamps_without_loss(self):
        approved_at = timezone.now() - timedelta(seconds=1)
        messages = [
            TextMessageFactory(status="approved", approved_at=approved_at)
            for _ in range(21)
        ]
        self._authorize()
        cursor = _encode_cursor(approved_at - timedelta(seconds=1))

        first = self.client.get("/monitor/feed/", {"cursor": cursor}).json()
        second = self.client.get("/monitor/feed/", {"cursor": first["cursor"]}).json()

        ids = {item["id"] for item in first["messages"] + second["messages"]}
        assert ids == {str(message.id) for message in messages}

    def test_feed_uses_stable_media_asset_url(self):
        asset = MediaAssetFactory(file__filename="asset.webp")
        message = TextMessageFactory(
            status="approved",
            approved_at=timezone.now(),
            media_type="photo",
            media_asset=asset,
        )
        self._authorize()

        payload = self.client.get("/monitor/feed/").json()

        assert payload["messages"][0]["id"] == str(message.id)
        assert payload["messages"][0]["media_url"].endswith(".webp")

    def test_invalid_cursor_is_rejected(self):
        self._authorize()
        response = self.client.get("/monitor/feed/", {"cursor": "tampered"})
        assert response.status_code == 400
