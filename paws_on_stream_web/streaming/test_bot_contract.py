from datetime import timedelta
from io import BytesIO
from urllib.parse import urlsplit

from core.factories import SettingsFactory
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from participants.factories import ParticipantFactory
from PIL import Image
from rest_framework.test import APIClient

from streaming.factories import EventFactory
from streaming.models import DisplayEvent, MediaAsset


def webp_bytes(*, size=(32, 24), mode="RGBA"):
    output = BytesIO()
    Image.new(mode, size, (255, 0, 0, 128)).save(output, format="WEBP")
    return output.getvalue()


def animated_webp_bytes():
    output = BytesIO()
    frames = [
        Image.new("RGBA", (16, 16), (255, 0, 0, 128)),
        Image.new("RGBA", (16, 16), (0, 255, 0, 128)),
    ]
    frames[0].save(
        output,
        format="WEBP",
        save_all=True,
        append_images=frames[1:],
        duration=[100, 200],
        loop=0,
    )
    return output.getvalue()


@override_settings(API_AUTH_TOKEN="test-token")
class MediaUploadAndMessageContractTest(TestCase):
    def test_media_upload_and_bot_message_create(self):
        client = APIClient()
        participant = ParticipantFactory(checked_in=True)
        EventFactory(is_active=True)
        SettingsFactory()

        upload = SimpleUploadedFile(
            "photo.webp",
            webp_bytes(),
            content_type="image/webp",
        )
        upload_response = client.post(
            "/api/v1/media/upload/",
            {
                "file": upload,
                "media_type": "photo",
                "telegram_file_id": "tg-file-1",
                "telegram_file_unique_id": "tg-unique-1",
            },
            format="multipart",
            HTTP_X_API_TOKEN="test-token",
        )
        assert upload_response.status_code == 201
        upload_data = upload_response.json()
        assert upload_data["status"] == "stored"
        assert "/api/v1/" not in upload_data["media_url"]
        assert not urlsplit(upload_data["media_url"]).path.startswith("//")

        duplicate_upload = SimpleUploadedFile(
            "photo.webp",
            webp_bytes(),
            content_type="image/webp",
        )
        duplicate_response = client.post(
            "/api/v1/media/upload/",
            {
                "file": duplicate_upload,
                "media_type": "photo",
                "telegram_file_id": "tg-file-1",
                "telegram_file_unique_id": "tg-unique-1",
            },
            format="multipart",
            HTTP_X_API_TOKEN="test-token",
        )
        assert duplicate_response.status_code == 200
        assert (
            duplicate_response.json()["media_asset_id"] == upload_data["media_asset_id"]
        )

        message_response = client.post(
            "/api/v1/message/",
            {
                "telegram_id": participant.telegram_id,
                "display_name": participant.display_name,
                "content": "",
                "media_type": "photo",
                "media_url": upload_data["media_url"],
                "media_asset_id": upload_data["media_asset_id"],
                "sticker_emoji": "",
            },
            format="json",
            HTTP_X_API_TOKEN="test-token",
        )
        assert message_response.status_code == 201, message_response.content
        message_data = message_response.json()
        assert message_data["participant"]["telegram_id"] == participant.telegram_id
        assert message_data["media_url"] == upload_data["media_url"]
        assert message_data["media_asset_id"] == upload_data["media_asset_id"]
        assert message_data["media_format"] == "webp"
        assert message_data["media_width"] == 32
        assert message_data["media_height"] == 24
        assert message_data["media_has_alpha"] is True

        approve_response = client.post(
            f"/api/v1/messages/{message_data['id']}/approve/",
            HTTP_X_API_TOKEN="test-token",
        )
        assert approve_response.status_code == 200

        display_response = client.get(
            "/api/v1/messages/display/", HTTP_X_API_TOKEN="test-token"
        )
        assert display_response.status_code == 200
        displayed = display_response.json()["results"][0]
        assert displayed["media_url"] == upload_data["media_url"]
        assert displayed["media_sha256"] == upload_data["sha256"]

    def test_upload_rejects_spoofed_mime_and_non_webp_content(self):
        client = APIClient()
        common = {
            "media_type": "photo",
            "telegram_file_id": "tg-file-bad",
            "telegram_file_unique_id": "tg-unique-bad",
        }
        wrong_mime = client.post(
            "/api/v1/media/upload/",
            {
                "file": SimpleUploadedFile(
                    "x.webp", webp_bytes(), content_type="image/jpeg"
                ),
                **common,
            },
            format="multipart",
            HTTP_X_API_TOKEN="test-token",
        )
        assert wrong_mime.status_code == 400
        spoofed = client.post(
            "/api/v1/media/upload/",
            {
                "file": SimpleUploadedFile(
                    "x.webp", b"not-webp", content_type="image/webp"
                ),
                **common,
            },
            format="multipart",
            HTTP_X_API_TOKEN="test-token",
        )
        assert spoofed.status_code == 400
        assert MediaAsset.objects.count() == 0

    def test_animated_webp_metadata_is_calculated_server_side(self):
        client = APIClient()
        response = client.post(
            "/api/v1/media/upload/",
            {
                "file": SimpleUploadedFile(
                    "animation.webp",
                    animated_webp_bytes(),
                    content_type="image/webp",
                ),
                "media_type": "gif",
                "telegram_file_id": "tg-animation",
                "telegram_file_unique_id": "tg-animation-unique",
            },
            format="multipart",
            HTTP_X_API_TOKEN="test-token",
        )
        assert response.status_code == 201
        assert response.json()["media_animated"] is True
        assert response.json()["media_frame_count"] == 2
        assert response.json()["media_duration_ms"] == 300

    def test_upload_rejects_oversized_dimensions_and_direct_media_url(self):
        client = APIClient()
        upload = client.post(
            "/api/v1/media/upload/",
            {
                "file": SimpleUploadedFile(
                    "wide.webp",
                    webp_bytes(size=(1281, 1), mode="RGB"),
                    content_type="image/webp",
                ),
                "media_type": "photo",
                "telegram_file_id": "tg-wide",
                "telegram_file_unique_id": "tg-wide-unique",
            },
            format="multipart",
            HTTP_X_API_TOKEN="test-token",
        )
        assert upload.status_code == 400

        participant = ParticipantFactory(checked_in=True)
        EventFactory(is_active=True)
        SettingsFactory()
        message = client.post(
            "/api/v1/message/",
            {
                "telegram_id": participant.telegram_id,
                "content": "",
                "media_type": "photo",
                "media_url": "https://attacker.invalid/video.mp4",
            },
            format="json",
            HTTP_X_API_TOKEN="test-token",
        )
        assert message.status_code == 400
        assert "media_asset_id" in message.json()

    def test_killswitch_display_event_is_persisted(self):
        from core.factories import DisplayDeviceFactory

        client = APIClient()
        device = DisplayDeviceFactory(device_id="pi-01")
        response = client.post(
            "/api/v1/events/killswitch/",
            {
                "device_id": device.device_id,
                "event_type": "killswitch",
                "occurred_at": "2026-07-20T08:30:00+02:00",
            },
            format="json",
            HTTP_X_API_TOKEN="test-token",
        )
        assert response.status_code == 201
        assert DisplayEvent.objects.get().device == device

    def test_muted_participant_message_is_rejected(self):
        client = APIClient()
        participant = ParticipantFactory(
            checked_in=True,
            muted_until=timezone.now() + timedelta(minutes=20),
        )
        EventFactory(is_active=True)
        SettingsFactory()

        response = client.post(
            "/api/v1/message/",
            {
                "telegram_id": participant.telegram_id,
                "display_name": participant.display_name,
                "content": "hello from muted user",
                "media_type": "text",
            },
            format="json",
            HTTP_X_API_TOKEN="test-token",
        )
        assert response.status_code == 400
        assert response.json()["status"] == "rejected"
        assert response.json()["reason"] == "muted"
