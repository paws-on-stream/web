from datetime import timedelta

from core.factories import SettingsFactory
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from participants.factories import ParticipantFactory
from rest_framework import status
from rest_framework.test import APIClient

from streaming.factories import EventFactory
from streaming.models import Message

TEST_TOKEN = "load-test-token"


@override_settings(
    API_AUTH_TOKEN=TEST_TOKEN,
    BOT_API_AUTH_TOKEN=TEST_TOKEN,
    DISPLAY_API_AUTH_TOKEN=TEST_TOKEN,
)
class MessageLoadContractTest(TestCase):
    def setUp(self):
        cache.clear()
        SettingsFactory(rate_limit_per_minute=10)
        EventFactory(
            is_active=True,
            allow_messages=True,
            starts_at=timezone.now() - timedelta(minutes=1),
            ends_at=timezone.now() + timedelta(minutes=30),
        )
        self.client = APIClient()
        self.client.credentials(HTTP_X_API_TOKEN=TEST_TOKEN)

    def _create_message(self, participant, content):
        return self.client.post(
            "/api/v1/message/",
            {
                "telegram_id": participant.telegram_id,
                "display_name": participant.display_name,
                "content": content,
                "media_type": "text",
            },
            format="json",
        )

    def test_accepts_101_messages_from_different_participants(self):
        participants = ParticipantFactory.create_batch(101, checked_in=True)

        responses = [
            self._create_message(participant, f"Load message {index}")
            for index, participant in enumerate(participants)
        ]

        assert all(
            response.status_code == status.HTTP_201_CREATED for response in responses
        )
        assert Message.objects.filter(status="pending").count() == 101

    def test_limits_one_participant_to_ten_messages_per_minute(self):
        participant = ParticipantFactory(checked_in=True)

        accepted = [
            self._create_message(participant, f"Rate-limit message {index}")
            for index in range(10)
        ]
        limited = self._create_message(participant, "Rate-limit message 11")

        assert all(
            response.status_code == status.HTTP_201_CREATED for response in accepted
        )
        assert limited.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert Message.objects.filter(participant=participant).count() == 10
