from django.test import TestCase
from streaming.factories import TextMessageFactory


class DashboardViewTest(TestCase):
    def setUp(self):
        self.message = TextMessageFactory(status="pending", content="Quick action")

    def test_dashboard_shows_quick_action_forms(self):
        response = self.client.get("/")
        assert response.status_code == 200
        assert 'name="message_id"' in response.content.decode()
        assert 'value="approve"' in response.content.decode()
        assert 'value="reject"' in response.content.decode()

    def test_approve_action_updates_message(self):
        response = self.client.post(
            "/",
            {
                "message_id": self.message.pk,
                "action": "approve",
            },
        )
        assert response.status_code == 302
        self.message.refresh_from_db()
        assert self.message.status == "approved"
        assert self.message.approved_at is not None

    def test_reject_action_updates_message(self):
        response = self.client.post(
            "/",
            {
                "message_id": self.message.pk,
                "action": "reject",
            },
        )
        assert response.status_code == 302
        self.message.refresh_from_db()
        assert self.message.status == "rejected"
        assert self.message.rejection_reason == "unknown"

    def test_missing_action_returns_400(self):
        response = self.client.post("/", {"message_id": self.message.pk})
        assert response.status_code == 400

    def test_message_content_is_escaped(self):
        TextMessageFactory(status="pending", content="<script>alert('xss')</script>")
        response = self.client.get("/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "&lt;script&gt;alert" in content
        assert "<script>alert('xss')</script>" not in content
