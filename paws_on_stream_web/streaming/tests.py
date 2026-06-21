import json
import uuid
from datetime import UTC, datetime, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from streaming.factories import EventFactory, TextMessageFactory
from streaming.middleware import ApiTokenMiddleware
from streaming.models import Event, Message


# Create your tests here.
class EventModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.event = EventFactory()

    def test_defaults(self):
        e = self.event
        self.assertFalse(e.is_active)
        self.assertTrue(e.allow_messages)
        self.assertEqual(e.display_mode, "")
        self.assertIsNone(e.scroll_speed_px)

    def test_str_is_human_readable(self):
        self.assertEqual(
            str(self.event),
            f"{self.event.name} ({self.event.starts_at.strftime('%Y-%m-%d %H:%M')})",
        )

    def test_default_ordering_desc_by_starts_at(self):
        Event.objects.all().delete()
        recent = EventFactory(starts_at=datetime.now(tz=UTC) + timedelta(days=5))
        older = EventFactory(starts_at=datetime.now(tz=UTC) + timedelta(days=1))
        qs = Event.objects.all()
        self.assertEqual(list(qs), [recent, older])


class MessageModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.message = TextMessageFactory()

    def test_media_type_choices(self):
        for choice, _ in Message.MEDIA_TYPES:
            self.message.media_type = choice
            self.message.full_clean()
        self.message.media_type = "invalid_choice"
        with self.assertRaises(ValidationError):
            self.message.full_clean()

    def test_status_choices(self):
        for status, _ in Message.STATUS_CHOICES:
            self.message.status = status
            self.message.full_clean()
        self.message.status = "garbage"
        with self.assertRaises(ValidationError):
            self.message.full_clean()

    def test_rejection_reason_choices(self):
        for reason, _ in Message.REJECTION_REASONS:
            self.message.rejection_reason = reason
            self.message.full_clean()
        self.message.rejection_reason = "unknown_reason"
        with self.assertRaises(ValidationError):
            self.message.full_clean()

    def test_uuid_is_generated(self):
        m = TextMessageFactory()
        self.assertIsNotNone(m.id)
        uuid.UUID(m.id)

    def test_str_is_human_readable(self):
        self.assertEqual(
            str(self.message),
            f"{self.message.participant.display_name}: {self.message.content[:50]}...",
        )


class ApiTokenMiddlewareTest(TestCase):
    """Tests for the X-API-Token authentication middleware."""

    TOKEN = "test-middleware-token"
    factory = RequestFactory()

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        settings.API_AUTH_TOKEN = cls.TOKEN

    def _response(self, path, method="GET", token=None):
        """Helper to build a request through middleware and return HttpResponse."""
        kwargs = {}
        if token is not None:
            kwargs["HTTP_X_API_TOKEN"] = token
        request = self.factory.get(path, **kwargs) if method == "GET" else self.factory.generic(method, path, **kwargs)

        def get_response(r):
            return HttpResponse(b'{"ok": true}', content_type="application/json")

        middleware = ApiTokenMiddleware(get_response)
        return middleware(request)

    # -- Happy path --

    def test_valid_token_returns_200(self):
        resp = self._response("/api/v1/messages/pending/", token=self.TOKEN)
        self.assertEqual(resp.status_code, 200)

    def test_valid_token_json_content_type(self):
        resp = self._response("/api/v1/messages/pending/", token=self.TOKEN)
        self.assertEqual(resp["Content-Type"], "application/json")

    def test_nested_api_path(self):
        resp = self._response("/api/v1/messages/42/approve/", token=self.TOKEN)
        self.assertEqual(resp.status_code, 200)

    # -- No token / wrong token --

    def test_no_token_returns_403(self):
        resp = self._response("/api/messages/")
        self.assertEqual(resp.status_code, 403)
        self.assertIn("Invalid or missing API token", resp.content.decode())

    def test_wrong_token_returns_403(self):
        resp = self._response("/api/settings/", token="wrong-token")
        self.assertEqual(resp.status_code, 403)

    def test_empty_token_returns_403(self):
        resp = self._response("/api/settings/", token="")
        self.assertEqual(resp.status_code, 403)

    # -- Non-API paths --

    def test_non_api_path_no_token(self):
        resp = self._response("/admin/")
        self.assertEqual(resp.status_code, 200)

    def test_root_path_no_token(self):
        resp = self._response("/")
        self.assertEqual(resp.status_code, 200)

    def test_api_path_for_no_api_prefix(self):
        """Path /apiary should not be matched."""
        resp = self._response("/apiary/messages/")
        self.assertEqual(resp.status_code, 200)

    # -- OPTIONS preflight --

    def test_options_preflight_skipped(self):
        resp = self._response("/api/v1/messages/", method="OPTIONS")
        self.assertEqual(resp.status_code, 200)

    def test_options_with_token_also_works(self):
        resp = self._response("/api/v1/messages/", method="OPTIONS", token=self.TOKEN)
        self.assertEqual(resp.status_code, 200)

    # -- JSON response format --

    def test_403_body_is_json(self):
        resp = self._response("/api/settings/")
        data = json.loads(resp.content)
        self.assertIn("error", data)

    def test_200_body_is_json(self):
        resp = self._response("/api/v1/messages/pending/", token=self.TOKEN)
        data = json.loads(resp.content)
        self.assertEqual(data, {"ok": True})
