from datetime import timedelta

from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from participants.factories import ParticipantFactory
from rest_framework import status
from rest_framework.test import APITestCase

from streaming.factories import EventFactory

TEST_TOKEN = "test-api-token"


@override_settings(API_AUTH_TOKEN=TEST_TOKEN, DEFAULT_THROTTLE_CLASSES=[])
class MessageCheckedInOverrideTest(APITestCase):
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

    def _create_message(self, content):
        return self.client.post(
            "/api/v1/messages/",
            {
                "participant_id": self.participant.id,
                "content": content,
                "event": self.event.id,
            },
            format="json",
        )

    def test_force_checked_in_override_allows_message(self):
        self.participant.checked_in = False
        self.participant.checked_in_override = True
        self.participant.save(update_fields=["checked_in", "checked_in_override"])

        response = self._create_message("Allowed by override")

        assert response.status_code == status.HTTP_201_CREATED

    def test_force_checked_out_override_rejects_message(self):
        self.participant.checked_in_override = False
        self.participant.save(update_fields=["checked_in_override"])

        response = self._create_message("Rejected by override")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["reason"] == "not_checkedin"
