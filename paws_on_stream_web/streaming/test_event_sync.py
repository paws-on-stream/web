from datetime import UTC, datetime
from io import StringIO
from unittest.mock import patch

from core.factories import SettingsFactory
from django.core.management import call_command
from django.test import TestCase

from streaming.event_sync import EventSyncError, apply_event_filter, sync_events
from streaming.models import Event


class EventSyncTest(TestCase):
    def setUp(self):
        SettingsFactory(
            event_api_url="https://sigma.example/api/events",
            event_api_jsonq_filter=(
                '[.[] | select(.attributes | type == "object" and has("live"))]'
            ),
        )
        self.payload = [
            {
                "id": 42,
                "name": "Opening",
                "start": "2026-08-05T12:00:00+02:00",
                "end": "2026-08-05T13:00:00+02:00",
                "attributes": {"live": True},
            },
            {
                "id": 43,
                "name": "Not live",
                "start": "2026-08-05T14:00:00+02:00",
                "end": "2026-08-05T15:00:00+02:00",
                "attributes": {},
            },
        ]

    def test_applies_configured_jq_expression(self):
        filtered = apply_event_filter(
            self.payload,
            '[.[] | select(.attributes | type == "object" and has("live"))]',
        )
        assert [event["id"] for event in filtered] == [42]

    @patch("streaming.event_sync.fetch_event_payload")
    def test_creates_then_idempotently_updates_events(self, fetch):
        fetch.return_value = self.payload
        first = sync_events()
        assert first.created == 1
        event = Event.objects.get(external_id="42")
        assert event.name == "Opening"

        self.payload[0]["name"] = "Opening Ceremony"
        second = sync_events()
        event.refresh_from_db()
        assert second.created == 0
        assert second.updated == 1
        assert Event.objects.count() == 1
        assert event.name == "Opening Ceremony"
        assert event.starts_at == datetime(2026, 8, 5, 10, tzinfo=UTC)

    def test_filter_must_return_an_array(self):
        with self.assertRaisesMessage(EventSyncError, "must return a JSON array"):
            apply_event_filter(self.payload, ".[0]")

    @patch("streaming.management.commands.sync_events.sync_events")
    def test_command_prints_summary(self, sync):
        from streaming.event_sync import EventSyncSummary

        sync.return_value = EventSyncSummary(2, 1, 1, 0)
        output = StringIO()
        call_command("sync_events", stdout=output)
        assert "received=2, created=1, updated=1, skipped=0" in output.getvalue()
