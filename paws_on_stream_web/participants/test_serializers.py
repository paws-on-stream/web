from django.test import TestCase

from participants.factories import ParticipantFactory
from participants.serializers import ParticipantCreateSerializer, ParticipantSerializer


class ParticipantSerializerTest(TestCase):
    def setUp(self):
        self.participant = ParticipantFactory()
        self.serializer = ParticipantSerializer(self.participant)

    def test_serializes_all_fields(self):
        data = self.serializer.data
        assert data["id"] == self.participant.id
        assert data["display_name"] == self.participant.display_name
        assert data["telegram_id"] == self.participant.telegram_id
        assert data["checked_in"] == self.participant.checked_in
        assert data["banned"] == self.participant.banned
        assert data["spam_count"] == self.participant.spam_count
        assert data["created_at"] is not None
        assert data["updated_at"] is not None

    def test_creation(self):
        data = {
            "telegram_id": 123456789,
            "display_name": "Test User",
            "checked_in": True,
        }
        serializer = ParticipantSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        instance = serializer.save()
        assert instance.telegram_id == 123456789
        assert instance.display_name == "Test User"
        assert instance.checked_in


class ParticipantCreateSerializerTest(TestCase):
    def test_validates_non_empty_display_name(self):
        data = {"telegram_id": 123, "display_name": "  "}
        serializer = ParticipantCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "display_name" in serializer.errors

    def test_strips_whitespace(self):
        data = {"telegram_id": 123, "display_name": "  Trimmed  "}
        serializer = ParticipantCreateSerializer(data=data)
        assert serializer.is_valid()
        instance = serializer.save()
        assert instance.display_name == "Trimmed"

    def test_uniqueness(self):
        ParticipantFactory(telegram_id=999)
        data = {"telegram_id": 999, "display_name": "Duplicate"}
        serializer = ParticipantCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "telegram_id" in serializer.errors
