from datetime import UTC, datetime, timedelta

from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from participants.factories import ParticipantFactory
from rest_framework import status
from rest_framework.test import APITestCase

from streaming.factories import EventFactory, TextMessageFactory

TEST_TOKEN = "test-api-token"


@override_settings(API_AUTH_TOKEN=TEST_TOKEN, DEFAULT_THROTTLE_CLASSES=[])
class EventListViewTest(APITestCase):
    def setUp(self):
        self.client.credentials(HTTP_X_API_TOKEN=TEST_TOKEN)
        cache.clear()
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


@override_settings(API_AUTH_TOKEN=TEST_TOKEN, DEFAULT_THROTTLE_CLASSES=[])
class EventRetrieveViewTest(APITestCase):
    def setUp(self):
        self.client.credentials(HTTP_X_API_TOKEN=TEST_TOKEN)
        cache.clear()
        self.event = EventFactory()

    def test_retrieve_event(self):
        response = self.client.get(f"/api/v1/events/{self.event.id}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == self.event.name
        assert response.json()["is_active"] == self.event.is_active

    def test_event_not_found(self):
        response = self.client.get("/api/v1/events/999/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@override_settings(API_AUTH_TOKEN=TEST_TOKEN, DEFAULT_THROTTLE_CLASSES=[])
class MessageListViewTest(APITestCase):
    def setUp(self):
        self.client.credentials(HTTP_X_API_TOKEN=TEST_TOKEN)
        cache.clear()
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


@override_settings(API_AUTH_TOKEN=TEST_TOKEN, DEFAULT_THROTTLE_CLASSES=[])
class MessageCreateViewTest(APITestCase):
    def setUp(self):
        self.client.credentials(HTTP_X_API_TOKEN=TEST_TOKEN)
        cache.clear()
        self.participant = ParticipantFactory(checked_in=True)
        self.event = EventFactory(
            is_active=True,
            allow_messages=True,
            starts_at=timezone.now() - timedelta(hours=1),
            ends_at=timezone.now() + timedelta(hours=1),
        )

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


@override_settings(API_AUTH_TOKEN=TEST_TOKEN, DEFAULT_THROTTLE_CLASSES=[])
class MessageApproveActionTest(APITestCase):
    def setUp(self):
        self.client.credentials(HTTP_X_API_TOKEN=TEST_TOKEN)
        cache.clear()
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
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already" in response.json()["status"][0].lower()


@override_settings(API_AUTH_TOKEN=TEST_TOKEN, DEFAULT_THROTTLE_CLASSES=[])
class MessageRejectActionTest(APITestCase):
    def setUp(self):
        self.client.credentials(HTTP_X_API_TOKEN=TEST_TOKEN)
        cache.clear()
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

    def test_reject_message_as_spam(self):
        response = self.client.post(
            f"/api/v1/messages/{self.message.id}/reject/",
            {"rejection_reason": "spam"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["rejection_reason"] == "spam"


@override_settings(API_AUTH_TOKEN=TEST_TOKEN, DEFAULT_THROTTLE_CLASSES=[])
class MessageViewSetAuthTest(APITestCase):
    def test_forbidden_without_token(self):
        response = self.client.get("/api/v1/messages/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_list_with_token(self):
        self.client.credentials(HTTP_X_API_TOKEN=TEST_TOKEN)
        cache.clear()
        response = self.client.get("/api/v1/messages/")
        assert response.status_code == status.HTTP_200_OK


@override_settings(
    API_AUTH_TOKEN=TEST_TOKEN,
    REST_FRAMEWORK={
        "DEFAULT_THROTTLE_CLASSES": ["streaming.throttling.UserRateThrottle"],
        "DEFAULT_THROTTLE_RATES": {"user": "1/min"},
    },
)
class DisplayActionsThrottleExemptionTest(APITestCase):
    def setUp(self):
        from core.factories import DisplayDeviceFactory

        self.client.credentials(HTTP_X_API_TOKEN=TEST_TOKEN, HTTP_X_DEVICE_ID="pi-01")
        cache.clear()
        self.participant = ParticipantFactory()
        self.event = EventFactory()
        self.message = TextMessageFactory(
            participant=self.participant,
            event=self.event,
            status="approved",
        )
        DisplayDeviceFactory(device_id="pi-01", hostname="pi-01.local")

    def test_display_messages_not_throttled(self):
        first = self.client.get("/api/v1/messages/display/")
        second = self.client.get("/api/v1/messages/display/")
        assert first.status_code == status.HTTP_200_OK
        assert second.status_code == status.HTTP_200_OK

    def test_mark_displayed_not_throttled(self):
        from core.models import DisplayLog

        payload = {"device_id": "pi-01"}
        first = self.client.post(
            f"/api/v1/messages/{self.message.id}/displayed/",
            payload,
            format="json",
        )
        second = self.client.post(
            f"/api/v1/messages/{self.message.id}/displayed/",
            payload,
            format="json",
        )
        assert first.status_code == status.HTTP_200_OK
        assert second.status_code == status.HTTP_200_OK
        assert DisplayLog.objects.filter(
            message=self.message,
            device__device_id="pi-01",
        ).exists()

    def test_mark_displayed_saves_duration_actual(self):
        from core.models import DisplayLog

        payload = {"device_id": "pi-01", "display_duration_actual": 9}
        response = self.client.post(
            f"/api/v1/messages/{self.message.id}/displayed/",
            payload,
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        log = DisplayLog.objects.get(message=self.message, device__device_id="pi-01")
        assert log.display_duration_actual == 9

    def test_ack_keeps_message_approved_for_other_displays(self):
        from core.factories import DisplayDeviceFactory

        DisplayDeviceFactory(device_id="pi-02", hostname="pi-02.local")
        response = self.client.post(
            f"/api/v1/messages/{self.message.id}/displayed/",
            {"device_id": "pi-01"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        self.message.refresh_from_db()
        assert self.message.status == "approved"
        assert self.message.displayed_at is not None

        self.client.credentials(
            HTTP_X_API_TOKEN=TEST_TOKEN,
            HTTP_X_DEVICE_ID="pi-02",
        )
        poll = self.client.get("/api/v1/messages/display/")
        ids = {item["id"] for item in poll.json()["results"]}
        assert str(self.message.id) in ids

    def test_ack_rejects_non_approved_message(self):
        self.message.status = "rejected"
        self.message.save(update_fields=["status"])
        response = self.client.post(
            f"/api/v1/messages/{self.message.id}/displayed/",
            {"device_id": "pi-01"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
