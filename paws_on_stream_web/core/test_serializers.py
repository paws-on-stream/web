from django.test import TestCase
from streaming.factories import TextMessageFactory

from core.factories import DisplayDeviceFactory, DisplayLogFactory, SettingsFactory
from core.serializers import (
    DisplayDeviceSerializer,
    DisplayLogSerializer,
    SettingsSerializer,
)


class SettingsSerializerTest(TestCase):
    def setUp(self):
        self.settings = SettingsFactory()
        self.serializer = SettingsSerializer(self.settings)

    def test_serializes_all_fields(self):
        data = self.serializer.data
        assert data["id"] == self.settings.id
        assert data["rate_limit_per_minute"] == self.settings.rate_limit_per_minute
        assert data["max_message_length"] == self.settings.max_message_length
        assert data["bot_status"] == self.settings.bot_status
        assert data["auto_approve"] == self.settings.auto_approve
        assert data["display_mode"] == self.settings.display_mode
        assert data["scroll_speed_px"] == self.settings.scroll_speed_px

    def test_update(self):
        data = {"rate_limit_per_minute": 20, "bot_status": "maintenance"}
        serializer = SettingsSerializer(self.settings, data=data, partial=True)
        assert serializer.is_valid(), serializer.errors
        instance = serializer.save()
        assert instance.rate_limit_per_minute == 20
        assert instance.bot_status == "maintenance"


class DisplayDeviceSerializerTest(TestCase):
    def setUp(self):
        self.device = DisplayDeviceFactory()
        self.serializer = DisplayDeviceSerializer(self.device)

    def test_serializes_all_fields(self):
        data = self.serializer.data
        assert data["id"] == self.device.id
        assert data["device_id"] == self.device.device_id
        assert data["hostname"] == self.device.hostname
        assert data["is_active"] == self.device.is_active

    def test_creation(self):
        data = {
            "device_id": "pi-test-001",
            "hostname": "display.local",
            "location": "Lobby",
            "is_active": True,
        }
        serializer = DisplayDeviceSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        instance = serializer.save()
        assert instance.device_id == "pi-test-001"
        assert instance.hostname == "display.local"
        assert instance.is_active

    def test_uniqueness(self):
        DisplayDeviceFactory(device_id="unique-id")
        data = {"device_id": "unique-id", "hostname": "dup.local"}
        serializer = DisplayDeviceSerializer(data=data)
        assert not serializer.is_valid()
        assert "device_id" in serializer.errors


class DisplayLogSerializerTest(TestCase):
    def setUp(self):
        self.log = DisplayLogFactory()
        self.serializer = DisplayLogSerializer(self.log)

    def test_serializes_all_fields(self):
        data = self.serializer.data
        assert data["id"] == self.log.id
        assert data["message"] == self.log.message.id
        assert data["device"] == self.log.device.id
        assert data["displayed_at"] is not None
        assert data["display_duration_actual"] == self.log.display_duration_actual

    def test_creation(self):
        message = TextMessageFactory()
        device = DisplayDeviceFactory()
        data = {"message": message.id, "device": device.id}
        serializer = DisplayLogSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        instance = serializer.save()
        assert str(instance.message.id) == str(message.id)
        assert str(instance.device.id) == str(device.id)
