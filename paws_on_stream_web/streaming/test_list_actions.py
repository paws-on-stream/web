from django.contrib.auth import get_user_model
from django.test import TestCase

from streaming.factories import EventFactory, TextMessageFactory
from streaming.models import Message


class MessageListActionHardeningTest(TestCase):
    def setUp(self):
        self.client.force_login(
            get_user_model().objects.create_user("staff", is_staff=True)
        )
        self.message = TextMessageFactory(status="pending")

    def test_rejects_unknown_action(self):
        response = self.client.post(
            "/streaming/messages/",
            {"action": "unknown", "select": [self.message.id]},
        )
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/streaming/messages/")

    def test_rejects_missing_selection(self):
        response = self.client.post(
            "/streaming/messages/",
            {"action": "approve"},
        )
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/streaming/messages/")

    def test_deletes_selected_messages(self):
        response = self.client.post(
            "/streaming/messages/",
            {"action": "delete", "select": [str(self.message.id)]},
        )
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/streaming/messages/")
        assert not Message.objects.filter(id=self.message.id).exists()

    def test_rejects_selected_messages_as_spam(self):
        response = self.client.post(
            "/streaming/messages/",
            {"action": "reject_spam", "select": [str(self.message.id)]},
        )
        assert response.status_code == 302
        self.message.refresh_from_db()
        assert self.message.status == "rejected"
        assert self.message.rejection_reason == "spam"


class EventListActionHardeningTest(TestCase):
    def setUp(self):
        self.client.force_login(
            get_user_model().objects.create_user("staff", is_staff=True)
        )
        self.event = EventFactory(is_active=False)

    def test_rejects_unknown_action(self):
        response = self.client.post(
            "/streaming/events/",
            {"action": "unknown", "select": [self.event.id]},
        )
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/streaming/events/")

    def test_rejects_missing_selection(self):
        response = self.client.post(
            "/streaming/events/",
            {"action": "activate"},
        )
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/streaming/events/")
