import uuid
from datetime import UTC, datetime, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase

from streaming.factories import EventFactory, TextMessageFactory
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
