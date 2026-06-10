from datetime import UTC, datetime, timedelta, timezone

from django.test import TestCase

from streaming.factories import EventFactory
from streaming.models import Event


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
