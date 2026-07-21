from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from streaming.factories import EventFactory

from core.factories import SettingsFactory


@override_settings(
    API_AUTH_TOKEN="admin-token",
    BOT_API_AUTH_TOKEN="bot-token",
    DISPLAY_API_AUTH_TOKEN="display-token",
    DEFAULT_THROTTLE_CLASSES=[],
)
class EffectiveDisplayModeTest(TestCase):
    url = "/api/v1/settings/effective-display-mode/"

    def setUp(self):
        SettingsFactory(display_mode="chat")

    def get_mode(self, token="bot-token"):
        return self.client.get(self.url, HTTP_X_API_TOKEN=token)

    def test_returns_global_mode_without_active_event(self):
        response = self.get_mode()

        assert response.status_code == 200
        assert response.json() == {
            "display_mode": "chat",
            "source": "global",
            "event_id": None,
        }

    def test_active_event_overrides_global_mode(self):
        now = timezone.now()
        event = EventFactory(
            is_active=True,
            allow_messages=True,
            starts_at=now - timedelta(hours=1),
            ends_at=now + timedelta(hours=1),
            display_mode="crawling",
        )

        response = self.get_mode()

        assert response.status_code == 200
        assert response.json() == {
            "display_mode": "crawling",
            "source": "event",
            "event_id": event.id,
        }

    def test_active_event_can_override_crawling_with_chat(self):
        settings = SettingsFactory()
        settings.display_mode = "crawling"
        settings.save(update_fields=["display_mode"])
        now = timezone.now()
        event = EventFactory(
            is_active=True,
            allow_messages=True,
            starts_at=now - timedelta(hours=1),
            ends_at=now + timedelta(hours=1),
            display_mode="chat",
        )

        response = self.get_mode()

        assert response.json() == {
            "display_mode": "chat",
            "source": "event",
            "event_id": event.id,
        }

    def test_empty_event_override_uses_global_mode(self):
        now = timezone.now()
        event = EventFactory(
            is_active=True,
            allow_messages=True,
            starts_at=now - timedelta(hours=1),
            ends_at=now + timedelta(hours=1),
            display_mode="",
        )

        response = self.get_mode()

        assert response.json() == {
            "display_mode": "chat",
            "source": "global",
            "event_id": event.id,
        }

    def test_inactive_or_out_of_window_event_is_ignored(self):
        now = timezone.now()
        EventFactory(
            is_active=False,
            allow_messages=True,
            starts_at=now - timedelta(hours=1),
            ends_at=now + timedelta(hours=1),
            display_mode="crawling",
        )

        response = self.get_mode()

        assert response.json()["display_mode"] == "chat"
        assert response.json()["event_id"] is None

    def test_out_of_window_event_is_ignored(self):
        now = timezone.now()
        EventFactory(
            is_active=True,
            allow_messages=True,
            starts_at=now - timedelta(hours=2),
            ends_at=now - timedelta(hours=1),
            display_mode="crawling",
        )

        response = self.get_mode()

        assert response.json()["display_mode"] == "chat"
        assert response.json()["event_id"] is None

    def test_event_without_messages_is_ignored(self):
        now = timezone.now()
        EventFactory(
            is_active=True,
            allow_messages=False,
            starts_at=now - timedelta(hours=1),
            ends_at=now + timedelta(hours=1),
            display_mode="crawling",
        )

        response = self.get_mode()

        assert response.json()["display_mode"] == "chat"
        assert response.json()["event_id"] is None

    def test_bot_token_can_only_read_effective_mode(self):
        allowed = self.get_mode()
        denied = self.client.get("/api/v1/settings/1/", HTTP_X_API_TOKEN="bot-token")

        assert allowed.status_code == 200
        assert denied.status_code == 403
