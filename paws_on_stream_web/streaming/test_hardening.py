from datetime import timedelta

from core.factories import SettingsFactory
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from participants.factories import ParticipantFactory
from rest_framework.test import APIClient

from streaming.factories import EventFactory
from streaming.models import Event


@override_settings(API_AUTH_TOKEN="admin-token")
class MessageBusinessRulesTest(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.client.credentials(HTTP_X_API_TOKEN="admin-token")
        self.participant = ParticipantFactory(checked_in=True)
        self.settings = SettingsFactory(require_event_active=True)

    def post_message(self, **extra):
        payload = {
            "telegram_id": self.participant.telegram_id,
            "content": "hello",
            "media_type": "text",
        }
        payload.update(extra)
        return self.client.post("/api/v1/message/", payload, format="json")

    def test_rejects_event_that_is_not_currently_open(self):
        EventFactory(
            is_active=True,
            starts_at=timezone.now() + timedelta(hours=1),
            ends_at=timezone.now() + timedelta(hours=2),
        )
        response = self.post_message()
        assert response.status_code == 400
        assert response.json()["reason"] == "no_event"

    def test_rejects_when_event_disallows_messages(self):
        EventFactory(
            is_active=True,
            allow_messages=False,
            starts_at=timezone.now() - timedelta(hours=1),
            ends_at=timezone.now() + timedelta(hours=1),
        )
        assert self.post_message().json()["reason"] == "no_event"

    def test_client_cannot_preapprove_message(self):
        EventFactory(
            is_active=True,
            starts_at=timezone.now() - timedelta(hours=1),
            ends_at=timezone.now() + timedelta(hours=1),
        )
        response = self.post_message(status="approved", spam_score=999)
        assert response.status_code == 201
        assert response.json()["status"] == "pending"
        assert response.json()["spam_score"] == 0

    def test_auto_approve_keeps_flagged_message_pending_and_updates_history(self):
        self.settings.auto_approve = True
        self.settings.spam_threshold = 0.7
        self.settings.save(update_fields=["auto_approve", "spam_threshold"])
        EventFactory(
            is_active=True,
            starts_at=timezone.now() - timedelta(hours=1),
            ends_at=timezone.now() + timedelta(hours=1),
        )
        response = self.post_message(
            content="aaaaaa " + "🐾" * 11 + " https://one.example https://two.example"
        )
        self.participant.refresh_from_db()
        assert response.status_code == 201
        assert response.json()["status"] == "pending"
        assert response.json()["spam_score"] == 0.7
        assert self.participant.spam_count == 1

    def test_auto_approve_approves_score_below_threshold(self):
        self.settings.auto_approve = True
        self.settings.spam_threshold = 0.7
        self.settings.save(update_fields=["auto_approve", "spam_threshold"])
        EventFactory(
            is_active=True,
            starts_at=timezone.now() - timedelta(hours=1),
            ends_at=timezone.now() + timedelta(hours=1),
        )
        response = self.post_message(content="Hallo zusammen")
        assert response.status_code == 201
        assert response.json()["status"] == "approved"

    def test_invalid_display_cursor_is_rejected(self):
        response = self.client.get("/api/v1/messages/display/?since=invalid")
        assert response.status_code == 400


@override_settings(API_AUTH_TOKEN="admin-token")
class EventApiRulesTest(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.client.credentials(HTTP_X_API_TOKEN="admin-token")

    def test_event_api_is_crud_and_keeps_only_one_active_event(self):
        now = timezone.now()
        payload = {
            "name": "First",
            "starts_at": now.isoformat(),
            "ends_at": (now + timedelta(hours=1)).isoformat(),
            "is_active": True,
            "allow_messages": True,
        }
        first = self.client.post("/api/v1/events/", payload, format="json")
        assert first.status_code == 201
        payload["name"] = "Second"
        second = self.client.post("/api/v1/events/", payload, format="json")
        assert second.status_code == 201, second.content
        assert Event.objects.filter(is_active=True).count() == 1
        assert Event.objects.get(pk=second.json()["id"]).is_active is True

    def test_rejects_invalid_event_interval(self):
        now = timezone.now().isoformat()
        response = self.client.post(
            "/api/v1/events/",
            {"name": "Invalid", "starts_at": now, "ends_at": now},
            format="json",
        )
        assert response.status_code == 400
