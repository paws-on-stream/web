from datetime import UTC, datetime, timedelta

from django.test import TestCase
from participants.factories import ParticipantFactory

from streaming.factories import EventFactory, TextMessageFactory
from streaming.serializers import (
    EventSerializer,
    MessageSerializer,
    ParticipantSummarySerializer,
)


class EventSerializerTest(TestCase):
    def setUp(self):
        self.event = EventFactory()
        self.serializer = EventSerializer(self.event)

    def test_serializes_all_fields(self):
        data = self.serializer.data
        assert data["id"] == self.event.id
        assert data["name"] == self.event.name
        assert data["is_active"] == self.event.is_active
        assert data["allow_messages"] == self.event.allow_messages
        assert data["display_mode"] == self.event.display_mode
        assert data["scroll_speed_px"] == self.event.scroll_speed_px
        assert data["starts_at"] is not None
        assert data["ends_at"] is not None

    def test_creation(self):
        data = {
            "name": "Test Event",
            "starts_at": datetime.now(tz=UTC).isoformat(),
            "ends_at": (datetime.now(tz=UTC) + timedelta(hours=2)).isoformat(),
            "is_active": True,
        }
        serializer = EventSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        instance = serializer.save()
        assert instance.name == "Test Event"
        assert instance.is_active


class ParticipantSummarySerializerTest(TestCase):
    def setUp(self):
        self.participant = ParticipantFactory()
        self.serializer = ParticipantSummarySerializer(self.participant)

    def test_compact_reference(self):
        data = self.serializer.data
        assert data["display_name"] == self.participant.display_name
        assert data["telegram_id"] == self.participant.telegram_id
        assert data["checked_in"] == self.participant.checked_in


class MessageSerializerTest(TestCase):
    def setUp(self):
        self.message = TextMessageFactory()
        self.serializer = MessageSerializer(self.message)

    def test_serializes_message_with_participant(self):
        data = self.serializer.data
        assert data["id"] is not None
        assert data["content"] == self.message.content
        assert data["status"] == self.message.status
        assert "participant" in data
        assert (
            data["participant"]["display_name"]
            == self.message.participant.display_name
        )

    def test_display_fields(self):
        data = self.serializer.data
        assert data["media_type_display"] == "Text"
        assert data["status_display"] == "Pending"

    def test_creation_with_participant_id(self):
        participant = ParticipantFactory()
        event = EventFactory()
        data = {
            "participant_id": participant.id,
            "content": "Test message",
            "event": event.id,
        }
        serializer = MessageSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        instance = serializer.save()
        assert instance.content == "Test message"
        assert instance.participant == participant
        assert instance.created_at is not None
