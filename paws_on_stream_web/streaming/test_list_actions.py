from django.test import TestCase

from streaming.factories import EventFactory, TextMessageFactory


class MessageListActionHardeningTest(TestCase):
    def setUp(self):
        self.message = TextMessageFactory(status="pending")

    def test_rejects_unknown_action(self):
        response = self.client.post(
            "/streaming/messages/",
            {"action": "unknown", "select": [self.message.id]},
        )
        assert response.status_code == 400

    def test_rejects_missing_selection(self):
        response = self.client.post(
            "/streaming/messages/",
            {"action": "approve"},
        )
        assert response.status_code == 400


class EventListActionHardeningTest(TestCase):
    def setUp(self):
        self.event = EventFactory(is_active=False)

    def test_rejects_unknown_action(self):
        response = self.client.post(
            "/streaming/events/",
            {"action": "unknown", "select": [self.event.id]},
        )
        assert response.status_code == 400

    def test_rejects_missing_selection(self):
        response = self.client.post(
            "/streaming/events/",
            {"action": "activate"},
        )
        assert response.status_code == 400
