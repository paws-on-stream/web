from io import BytesIO
from unittest.mock import patch

from core.factories import SettingsFactory
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from participants.factories import ParticipantFactory
from PIL import Image
from rest_framework.test import APIClient


def webp_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGBA", (16, 16), (1, 2, 3, 255)).save(output, format="WEBP")
    return output.getvalue()


@override_settings(
    API_AUTH_TOKEN="admin-token",
    BOT_API_AUTH_TOKEN="bot-token",
    REST_FRAMEWORK={
        "DEFAULT_THROTTLE_CLASSES": ["streaming.throttling.UserRateThrottle"],
        "DEFAULT_THROTTLE_RATES": {"user": "1/min"},
    },
)
class BotTransportThrottleTest(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.client.credentials(HTTP_X_API_TOKEN="bot-token")
        self.participant = ParticipantFactory(checked_in=True)
        settings = SettingsFactory(require_event_active=False)
        settings.rate_limit_per_minute = 1
        settings.save(update_fields=("rate_limit_per_minute",))

    def _upload(self, suffix: str):
        return self.client.post(
            "/api/v1/media/upload/",
            {
                "file": SimpleUploadedFile(
                    f"image-{suffix}.webp", webp_bytes(), content_type="image/webp"
                ),
                "media_type": "photo",
                "telegram_file_id": f"file-{suffix}",
                "telegram_file_unique_id": f"unique-{suffix}",
            },
            format="multipart",
        )

    def test_bot_media_transport_is_not_globally_throttled(self):
        assert self._upload("one").status_code == 201
        assert self._upload("two").status_code == 200

    @patch("participants.views.sync_participant_by_telegram_id")
    def test_bot_participant_status_transport_is_not_globally_throttled(self, sync):
        sync.return_value = (self.participant, False, False)
        path = f"/api/v1/participants/{self.participant.telegram_id}/check_status/"
        assert self.client.post(path).status_code == 200
        assert self.client.post(path).status_code == 200

    def test_bot_message_limit_remains_per_participant(self):
        payload = {
            "telegram_id": self.participant.telegram_id,
            "display_name": self.participant.display_name,
            "content": "hello",
            "media_type": "text",
        }
        assert (
            self.client.post("/api/v1/message/", payload, format="json").status_code
            == 201
        )
        response = self.client.post("/api/v1/message/", payload, format="json")
        assert response.status_code == 429, response.content
