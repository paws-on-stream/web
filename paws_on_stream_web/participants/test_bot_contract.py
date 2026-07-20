from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from participants.factories import ParticipantFactory


@override_settings(API_AUTH_TOKEN="test-token")
class ParticipantBotContractTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.participant = ParticipantFactory(checked_in=True)

    def test_ban_alias_updates_participant(self):
        response = self.client.post(
            f"/api/v1/participant/{self.participant.telegram_id}/ban/",
            HTTP_X_API_TOKEN="test-token",
        )
        assert response.status_code == 200
        self.participant.refresh_from_db()
        assert self.participant.banned is True

    def test_mute_alias_updates_participant(self):
        response = self.client.post(
            f"/api/v1/participant/{self.participant.telegram_id}/mute/",
            {"minutes": 15},
            format="json",
            HTTP_X_API_TOKEN="test-token",
        )
        assert response.status_code == 200
        self.participant.refresh_from_db()
        assert self.participant.muted_until is not None
        assert self.participant.muted_until > timezone.now()
