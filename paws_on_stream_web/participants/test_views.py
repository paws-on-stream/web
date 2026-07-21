from unittest.mock import patch

from django.core.cache import cache
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from participants.factories import ParticipantFactory
from participants.models import Participant

TEST_TOKEN = "test-api-token"


@override_settings(API_AUTH_TOKEN=TEST_TOKEN, DEFAULT_THROTTLE_CLASSES=[])
class ParticipantListViewTest(APITestCase):
    def setUp(self):
        self.client.credentials(HTTP_X_API_TOKEN=TEST_TOKEN)
        cache.clear()
        self.participants = ParticipantFactory.create_batch(3)

    def test_list_participants(self):
        response = self.client.get("/api/v1/participants/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()["results"]) == 3

    def test_participant_data_structure(self):
        response = self.client.get("/api/v1/participants/")
        participant = response.json()["results"][0]
        assert "id" in participant
        assert "telegram_id" in participant
        assert "display_name" in participant
        assert "checked_in" in participant
        assert "banned" in participant
        assert "spam_count" in participant
        assert "created_at" in participant
        assert "updated_at" in participant


@override_settings(API_AUTH_TOKEN=TEST_TOKEN, DEFAULT_THROTTLE_CLASSES=[])
class ParticipantRetrieveViewTest(APITestCase):
    def setUp(self):
        self.client.credentials(HTTP_X_API_TOKEN=TEST_TOKEN)
        cache.clear()
        self.participant = ParticipantFactory()

    def test_retrieve_participant(self):
        response = self.client.get(f"/api/v1/participants/{self.participant.id}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["telegram_id"] == self.participant.telegram_id
        assert response.json()["display_name"] == self.participant.display_name

    def test_participant_not_found(self):
        response = self.client.get("/api/v1/participants/999/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@override_settings(API_AUTH_TOKEN=TEST_TOKEN, DEFAULT_THROTTLE_CLASSES=[])
class ParticipantCreateViewTest(APITestCase):
    def setUp(self):
        self.client.credentials(HTTP_X_API_TOKEN=TEST_TOKEN)
        cache.clear()

    def test_create_participant(self):
        data = {
            "telegram_id": 123456789,
            "display_name": "New Participant",
        }
        response = self.client.post("/api/v1/participants/", data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["telegram_id"] == 123456789
        assert response.json()["display_name"] == "New Participant"
        assert Participant.objects.filter(telegram_id=123456789).exists()

    def test_create_duplicate_telegram_id(self):
        ParticipantFactory(telegram_id=999)
        data = {"telegram_id": 999, "display_name": "Duplicate"}
        response = self.client.post("/api/v1/participants/", data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_blank_display_name(self):
        data = {"telegram_id": 222, "display_name": "  "}
        response = self.client.post("/api/v1/participants/", data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "display_name" in response.json()


@override_settings(API_AUTH_TOKEN=TEST_TOKEN, DEFAULT_THROTTLE_CLASSES=[])
class ParticipantUpdateViewTest(APITestCase):
    def setUp(self):
        self.client.credentials(HTTP_X_API_TOKEN=TEST_TOKEN)
        cache.clear()
        self.participant = ParticipantFactory()

    def test_partial_update(self):
        data = {"display_name": "Updated Name"}
        response = self.client.patch(
            f"/api/v1/participants/{self.participant.id}/", data, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["display_name"] == "Updated Name"
        self.participant.refresh_from_db()
        assert self.participant.display_name == "Updated Name"

    def test_full_update(self):
        data = {
            "telegram_id": self.participant.telegram_id,
            "display_name": "Fully Updated",
            "checked_in": True,
            "banned": True,
            "spam_count": 5,
        }
        response = self.client.put(
            f"/api/v1/participants/{self.participant.id}/", data, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["display_name"] == "Fully Updated"
        assert response.json()["checked_in"] is True
        assert response.json()["banned"] is True

    def test_update_not_found(self):
        data = {"display_name": "Updated"}
        response = self.client.patch("/api/v1/participants/999/", data, format="json")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@override_settings(API_AUTH_TOKEN=TEST_TOKEN, DEFAULT_THROTTLE_CLASSES=[])
class ParticipantDeleteViewTest(APITestCase):
    def setUp(self):
        self.client.credentials(HTTP_X_API_TOKEN=TEST_TOKEN)
        cache.clear()
        self.participant = ParticipantFactory()

    def test_delete_participant(self):
        response = self.client.delete(f"/api/v1/participants/{self.participant.id}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Participant.objects.filter(id=self.participant.id).exists()

    def test_delete_not_found(self):
        response = self.client.delete("/api/v1/participants/999/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@override_settings(API_AUTH_TOKEN=TEST_TOKEN, DEFAULT_THROTTLE_CLASSES=[])
class ParticipantRegStatusCheckViewTest(APITestCase):
    def setUp(self):
        self.client.credentials(HTTP_X_API_TOKEN=TEST_TOKEN)
        cache.clear()
        self.participant = ParticipantFactory(telegram_id=111222333, checked_in=False)

    @patch("participants.views.sync_participant_by_telegram_id")
    def test_check_status_success(self, mock_sync):
        mock_sync.return_value = (self.participant, True, False)
        response = self.client.post("/api/v1/participants/111222333/check_status/")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["changed"] is True
        assert response.json()["created"] is False
        assert response.json()["participant"]["telegram_id"] == 111222333

    @patch("participants.reg_sync.fetch_reg_status")
    def test_check_status_creates_unknown_local_participant(self, mock_fetch):
        from participants.reg_sync import parse_reg_status

        mock_fetch.return_value = parse_reg_status(
            {
                "checked_in": True,
                "reg_id": 42,
                "display_name": "Reg Attendee",
            }
        )
        response = self.client.post("/api/v1/participants/999999999/check_status/")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["created"] is True
        participant = Participant.objects.get(telegram_id=999999999)
        assert participant.display_name == "Reg Attendee"
        assert participant.checked_in is True

    @patch("participants.views.sync_participant_by_telegram_id")
    def test_check_status_upstream_error(self, mock_sync):
        from participants.reg_sync import RegSyncError

        mock_sync.side_effect = RegSyncError("Registration API is unreachable.")
        response = self.client.post("/api/v1/participants/111222333/check_status/")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["changed"] is False
        assert response.json()["fallback"] is True
        assert response.json()["participant"]["telegram_id"] == 111222333
        assert "unreachable" in response.json()["detail"]

    def test_check_status_get_is_not_allowed(self):
        response = self.client.get("/api/v1/participants/111222333/check_status/")
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    @patch("participants.views.sync_participant_by_telegram_id")
    def test_unknown_participant_upstream_failure_is_bad_gateway(self, mock_sync):
        from participants.reg_sync import RegSyncError

        self.participant.delete()
        mock_sync.side_effect = RegSyncError("Registration API is unreachable.")
        response = self.client.post("/api/v1/participants/999999999/check_status/")
        assert response.status_code == status.HTTP_502_BAD_GATEWAY
