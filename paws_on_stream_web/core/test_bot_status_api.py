from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from streaming.factories import EventFactory

from core.factories import SettingsFactory


@override_settings(API_AUTH_TOKEN="admin-token", BOT_API_AUTH_TOKEN="bot-token")
class BotStatusAPIViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_X_API_TOKEN="bot-token")
        self.settings = SettingsFactory(bot_status="online", require_event_active=True)

    def test_bot_can_read_active_event_and_message_state(self):
        event = EventFactory(
            is_active=True,
            allow_messages=True,
            display_mode="crawling",
            starts_at=timezone.now() - timedelta(minutes=5),
            ends_at=timezone.now() + timedelta(minutes=5),
        )

        response = self.client.get("/api/v1/bot/status/")

        assert response.status_code == 200
        assert response.json() == {
            "bot_status": "online",
            "messages_accepted": True,
            "messages_reason": None,
            "display_mode": "crawling",
            "active_event": {
                "id": event.id,
                "name": event.name,
                "allow_messages": True,
                "starts_at": event.starts_at.isoformat(),
                "ends_at": event.ends_at.isoformat(),
            },
        }

    def test_bot_can_update_only_central_bot_status(self):
        response = self.client.put(
            "/api/v1/bot/status/", {"bot_status": "maintenance"}, format="json"
        )

        assert response.status_code == 200
        self.settings.refresh_from_db()
        assert self.settings.bot_status == "maintenance"
        assert response.json()["messages_accepted"] is False
        assert response.json()["messages_reason"] == "maintenance"

    def test_rejects_invalid_status(self):
        response = self.client.put(
            "/api/v1/bot/status/", {"bot_status": "invalid"}, format="json"
        )
        assert response.status_code == 400

    def test_display_token_cannot_access_bot_status(self):
        self.client.credentials(HTTP_X_API_TOKEN="display-token")
        response = self.client.get("/api/v1/bot/status/")
        assert response.status_code == 403
