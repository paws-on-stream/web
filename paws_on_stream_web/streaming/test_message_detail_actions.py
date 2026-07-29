from django.contrib.auth import get_user_model
from django.test import TestCase

from streaming.factories import TextMessageFactory
from streaming.models import Message


class MessageDetailActionTest(TestCase):
    def setUp(self):
        self.client.force_login(
            get_user_model().objects.create_user("staff", is_staff=True)
        )
        self.message = TextMessageFactory(status="pending")
        self.url = f"/streaming/messages/{self.message.pk}/"

    def test_approve_action(self):
        response = self.client.post(self.url, {"action": "approve"})
        assert response.status_code == 302
        self.message.refresh_from_db()
        assert self.message.status == "approved"
        assert self.message.approved_at is not None

    def test_reject_action(self):
        response = self.client.post(self.url, {"action": "reject"})
        assert response.status_code == 302
        self.message.refresh_from_db()
        assert self.message.status == "rejected"
        assert self.message.rejection_reason == "moderator_other"

    def test_reject_as_spam_action(self):
        response = self.client.post(self.url, {"action": "reject_spam"})
        assert response.status_code == 302
        self.message.refresh_from_db()
        assert self.message.status == "rejected"
        assert self.message.rejection_reason == "spam"

    def test_delete_action(self):
        message_id = self.message.pk
        response = self.client.post(self.url, {"action": "delete"})
        assert response.status_code == 302
        assert not Message.objects.filter(pk=message_id).exists()

    def test_unknown_action_returns_400(self):
        response = self.client.post(self.url, {"action": "wat"})
        assert response.status_code == 400
