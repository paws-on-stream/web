from django.contrib.auth import get_user_model
from django.test import TestCase
from participants.factories import ParticipantFactory
from streaming.factories import EventFactory, TextMessageFactory


class DashboardViewTest(TestCase):
    def setUp(self):
        self.client.force_login(
            get_user_model().objects.create_user("staff", is_staff=True)
        )
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

    def test_unsupported_action_returns_400(self):
        response = self.client.post(
            "/",
            {
                "message_id": self.message.pk,
                "action": "unsupported",
            },
        )
        assert response.status_code == 400

    def test_missing_message_returns_404(self):
        response = self.client.post(
            "/",
            {
                "message_id": "00000000-0000-0000-0000-000000000000",
                "action": "approve",
            },
        )
        assert response.status_code == 404

    def test_approve_non_pending_message_returns_400(self):
        approved_message = TextMessageFactory(status="approved")
        response = self.client.post(
            "/",
            {
                "message_id": approved_message.pk,
                "action": "approve",
            },
        )
        assert response.status_code == 400

    def test_reject_non_pending_message_returns_400(self):
        rejected_message = TextMessageFactory(status="rejected")
        response = self.client.post(
            "/",
            {
                "message_id": rejected_message.pk,
                "action": "reject",
            },
        )
        assert response.status_code == 400

    def test_message_content_is_escaped(self):
        TextMessageFactory(status="pending", content="<script>alert('xss')</script>")
        response = self.client.get("/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "&lt;script&gt;alert" in content
        assert "<script>alert('xss')</script>" not in content

    def test_dashboard_shows_only_pending_messages(self):
        pending_message = TextMessageFactory(
            status="pending",
            content="pending-visible",
        )
        TextMessageFactory(status="approved", content="approved-hidden")

        response = self.client.get("/")
        assert response.status_code == 200
        content = response.content.decode()
        assert pending_message.content in content
        assert "approved-hidden" not in content

    def test_kpis_are_calculated_in_context(self):
        ParticipantFactory.create_batch(2)
        TextMessageFactory.create_batch(3, status="pending")
        TextMessageFactory.create_batch(2, status="approved")

        response = self.client.get("/")
        assert response.status_code == 200
        kpis = {item["id"]: item["value"] for item in response.context["kpis"]}
        assert kpis["msg-pending"] == 4  # includes self.message from setUp
        assert kpis["participants"] >= 3  # includes participants from message factories
        assert kpis["msg-rate"] >= 0

    def test_live_endpoint_returns_only_pending_messages_and_kpis(self):
        event = EventFactory(name="Live-Event")
        pending = TextMessageFactory(
            status="pending", content="live-pending", event=event
        )
        TextMessageFactory(status="approved", content="live-approved")

        response = self.client.get("/live/")

        assert response.status_code == 200
        payload = response.json()
        assert payload["kpis"]["pending_count"] >= 2
        assert {item["id"] for item in payload["messages"]} >= {str(pending.pk)}
        assert all(item["status"] == "pending" for item in payload["messages"])
        message = next(
            item for item in payload["messages"] if item["id"] == str(pending.pk)
        )
        assert message["event_name"] == "Live-Event"
        assert "no-cache" in response.headers["Cache-Control"]

    def test_live_endpoint_limits_queue_to_newest_50_messages(self):
        TextMessageFactory.create_batch(51, status="pending")

        response = self.client.get("/live/")

        assert response.status_code == 200
        assert len(response.json()["messages"]) == 50

    def test_live_endpoint_requires_staff(self):
        self.client.logout()
        response = self.client.get("/live/")
        assert response.status_code == 403

    def test_json_message_action_returns_without_redirect(self):
        response = self.client.post(
            "/",
            {"message_id": self.message.pk, "action": "approve"},
            HTTP_ACCEPT="application/json",
        )
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "message_id": str(self.message.pk)}
