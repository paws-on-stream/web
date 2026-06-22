from datetime import UTC, datetime

from django.test import override_settings
from participants.factories import ParticipantFactory
from rest_framework import status
from rest_framework.test import APITestCase

from streaming.factories import EventFactory, TextMessageFactory

TEST_TOKEN = "test-api-token"


@override_settings(API_AUTH_TOKEN=TEST_TOKEN)
class EventListViewTest(APITestCase):
    def setUp(self):
        self.client.credentials(HTTP_X_API_TOKEN=TEST_TOKEN)
        self.events = EventFactory.create_batch(3)

    def test_list_events(self):
        response = self.client.get("/api/v1/events/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()["results"]) == 3

    def test_event_data_structure(self):
        response = self.client.get("/api/v1/events/")
        event = response.json()["results"][0]
        assert "id" in event
        assert "name" in event
        assert "starts_at" in event
        assert "ends_at" in event
        assert "is_active" in event
        assert "allow_messages" in event
        assert "display_mode" in event
        assert "scroll_speed_px" in event


@override_settings(API_AUTH_TOKEN=TEST_TOKEN)
class EventRetrieveViewTest(APITestCase):
    def setUp(self):
        self.client.credentials(HTTP_X_API_TOKEN=TEST_TOKEN)
        self.event = EventFactory()

    def test_retrieve_event(self):
        response = self.client.get(f"/api/v1/events/{self.event.id}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == self.event.name
        assert response.json()["is_active"] == self.event.is_active

    def test_event_not_found(self):
        response = self.client.get("/api/v1/events/999/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@override_settings(API_AUTH_TOKEN=TEST_TOKEN)
class MessageListViewTest(APITestCase):
    def setUp(self):
        self.client.credentials(HTTP_X_API_TOKEN=TEST_TOKEN)
        self.participant = ParticipantFactory()
        self.event = EventFactory()

    def test_list_messages(self):
        TextMessageFactory.create_batch(
            3, participant=self.participant, event=self.event
        )
        response = self.client.get("/api/v1/messages/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()["results"]) == 3

    def test_pending_filter(self):
        TextMessageFactory.create_batch(
            3, participant=self.participant, event=self.event, status="pending"
        )
        TextMessageFactory.create_batch(
            2, participant=self.participant, event=self.event, status="approved"
        )
        response = self.client.get("/api/v1/messages/pending/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()["results"]) == 3

    def test_displayed_filter(self):
        TextMessageFactory.create_batch(
            3, participant=self.participant, event=self.event, status="displayed"
        )
        TextMessageFactory.create_batch(
            2, participant=self.participant, event=self.event, status="pending"
        )
        response = self.client.get("/api/v1/messages/displayed/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()["results"]) == 3


@override_settings(API_AUTH_TOKEN=TEST_TOKEN)
class MessageCreateViewTest(APITestCase):
    def setUp(self):
        self.client.credentials(HTTP_X_API_TOKEN=TEST_TOKEN)
        self.participant = ParticipantFactory()
        self.event = EventFactory()

    def test_create_message(self):
        data = {
            "participant_id": self.participant.id,
            "content": "Hello from API!",
            "event": self.event.id,
        }
        response = self.client.post("/api/v1/messages/", data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["content"] == "Hello from API!"
        assert response.json()["status"] == "pending"


@override_settings(API_AUTH_TOKEN=TEST_TOKEN)
class MessageApproveActionTest(APITestCase):
    def setUp(self):
        self.client.credentials(HTTP_X_API_TOKEN=TEST_TOKEN)
        self.participant = ParticipantFactory()
        self.message = TextMessageFactory(
            participant=self.participant,
            content="Test message",
            status="pending",
        )

    def test_approve_message(self):
        response = self.client.post(f"/api/v1/messages/{self.message.id}/approve/")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "approved"
        assert response.json()["approved_at"] is not None
        self.message.refresh_from_db()
        assert self.message.status == "approved"
        assert self.message.approved_at is not None

    def test_approve_already_approved(self):
        self.message.status = "approved"
        self.message.approved_at = datetime.now(tz=UTC)
        self.message.save()
        response = self.client.post(f"/api/v1/messages/{self.message.id}/approve/")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "approved"


@override_settings(API_AUTH_TOKEN=TEST_TOKEN)
class MessageRejectActionTest(APITestCase):
    def setUp(self):
        self.client.credentials(HTTP_X_API_TOKEN=TEST_TOKEN)
        self.participant = ParticipantFactory()
        self.message = TextMessageFactory(
            participant=self.participant,
            content="Test message",
            status="pending",
        )

    def test_reject_message_default_reason(self):
        response = self.client.post(f"/api/v1/messages/{self.message.id}/reject/")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "rejected"
        assert response.json()["rejection_reason"] == "unknown"
        self.message.refresh_from_db()
        assert self.message.status == "rejected"

    def test_reject_message_custom_reason(self):
        data = {"rejection_reason": "no_event"}
        response = self.client.post(
            f"/api/v1/messages/{self.message.id}/reject/", data, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "rejected"
        assert response.json()["rejection_reason"] == "no_event"


@override_settings(API_AUTH_TOKEN=TEST_TOKEN)
class MessageDisplayActionTest(APITestCase):
    def setUp(self):
        self.client.credentials(HTTP_X_API_TOKEN=TEST_TOKEN)
        self.participant = ParticipantFactory()
        self.message = TextMessageFactory(
            participant=self.participant,
            content="Test message",
            status="approved",
        )

    def test_display_message(self):
        response = self.client.post(f"/api/v1/messages/{self.message.id}/display/")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "displayed"
        assert response.json()["displayed_at"] is not None
        self.message.refresh_from_db()
        assert self.message.status == "displayed"
        assert self.message.displayed_at is not None


@override_settings(API_AUTH_TOKEN=TEST_TOKEN)
class MessageViewSetAuthTest(APITestCase):
    def test_forbidden_without_token(self):
        response = self.client.get("/api/v1/messages/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_list_with_token(self):
        self.client.credentials(HTTP_X_API_TOKEN=TEST_TOKEN)
        response = self.client.get("/api/v1/messages/")
        assert response.status_code == status.HTTP_200_OK
