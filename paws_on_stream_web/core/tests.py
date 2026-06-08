from datetime import datetime, timezone

from django.db import IntegrityError
from django.test import TestCase
from core.models import Settings, DisplayDevice, DisplayLog
from django.core.exceptions import ValidationError
from core.factories import SettingsFactory, DisplayDeviceFactory, DisplayLogFactory


# Create your tests here.

class SettingsModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.settings = SettingsFactory(id=1)

    def test_defaults_are_set(self):
        s = Settings.objects.get(id=1)
        self.assertEqual(s.rate_limit_per_minute, 10)
        self.assertEqual(s.max_message_length, 4096)
        self.assertEqual(s.bot_status, "online")
        self.assertEqual(s.overlay_theme, "default")
        self.assertEqual(s.overlay_font_size, 24)
        self.assertFalse(s.auto_approve)
        self.assertEqual(s.display_duration_sec, 8)
        self.assertEqual(s.reg_api_url, "")
        self.assertEqual(s.reg_api_key, "")
        self.assertEqual(s.status_check_interval, 300)
        self.assertTrue(s.require_event_active)
        self.assertEqual(s.display_mode, "chat")
        self.assertEqual(s.scroll_speed_px, 3)

    def test_get_settings_returns_the_same_instance(self):
        first = Settings.get_settings()
        second = Settings.get_settings()
        self.assertIs(first.pk, second.pk)
        self.assertEqual(first.pk, 1)
        self.assertEqual(Settings.objects.count(), 1)


    def test_bot_status_choice_validation(self):
        s = Settings.objects.get(pk=1)
        s.bot_status = "offline"
        s.full_clean()
        s.bot_status = "invalid_choice"
        with self.assertRaises(ValidationError):
            s.full_clean()

    def test_url_field_allows_blank(self):
        s = Settings.objects.get(pk=1)
        s.reg_api_url = ""
        s.full_clean()
        s.reg_api_url = "not a url"
        with self.assertRaises(ValidationError):
            s.full_clean()

    def test_updated_at_is_updated_on_save(self):
        s = Settings.objects.get(pk=1)
        old_ts = s.updated_at
        s.rate_limit_per_minute = 20
        s.save()
        s.refresh_from_db()
        self.assertGreater(s.updated_at, old_ts)

    def test_str_returns_human_readable(self):
        s = Settings.objects.get(pk=1)
        self.assertEqual(str(s), "Application Settings")


class DisplayDeviceModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.displayDevice = DisplayDeviceFactory(device_id="test-device", hostname="test-device")

    def test_str_returns_human_readable(self):
        self.assertEqual(str(self.displayDevice), f"{self.displayDevice.hostname} ({self.displayDevice.device_id})")

    def test_defaults_are_set(self):
        d = DisplayDeviceFactory(device_id="test-device2")
        self.assertTrue(d.is_active)
        self.assertIsNone(d.location)
        self.assertIsNone(d.last_seen)

    def test_device_id_is_unique(self):
        with self.assertRaises(IntegrityError):
            DisplayDevice.objects.create(device_id="test-device", hostname="test-device")

    def test_null_and_blank_fields(self):
        self.displayDevice.location = None
        self.displayDevice.last_seen = None
        self.displayDevice.full_clean()
        self.displayDevice.save()
        self.assertIsNone(self.displayDevice.location)
        self.assertIsNone(self.displayDevice.last_seen)

    def test_ordering_by_device_id(self):
        DisplayDevice.objects.create(device_id="test-device2", hostname="test-device")
        DisplayDevice.objects.create(device_id="test-device3", hostname="test-device")
        DisplayDevice.objects.create(device_id="test-device4", hostname="test-device")

        ids = list(DisplayDevice.objects.all().values_list("device_id", flat=True))
        self.assertEqual(ids, sorted(ids))

    def test_last_seen_validation(self):
        self.displayDevice.last_seen = "not a datetime"
        with self.assertRaises(ValidationError):
            self.displayDevice.full_clean()

    def test_max_length_device_id(self):
        d = DisplayDeviceFactory()
        d.device_id = "x" * 33
        with self.assertRaises(ValidationError):
            d.full_clean()

    def test_max_length_hostname(self):
        d = DisplayDeviceFactory()
        d.hostname = "x" * 129
        with self.assertRaises(ValidationError):
            d.full_clean()

    def test_max_length_location(self):
        d = DisplayDeviceFactory()
        d.location = "x" * 65
        with self.assertRaises(ValidationError):
            d.full_clean()

class DisplayLogModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.displayLog = DisplayLogFactory()

    def test_str_returns_human_readable(self):
        self.assertEqual(str(self.displayLog), f"{self.displayLog.message.participant.display_name} on {self.displayLog.device.device_id} at {self.displayLog.displayed_at}")

    def test_displayed_at_is_set_on_create(self):
        now = datetime.now(tz=timezone.utc)
        log = DisplayLogFactory()
        self.assertIsNotNone(log.displayed_at)
        # Das Feld darf **nicht** vor dem Erstellzeitpunkt liegen
        self.assertGreaterEqual(log.displayed_at, now)

    def test_display_duration_can_be_null(self):
        log = DisplayLogFactory(display_duration_actual=None)
        log.full_clean()   # darf keinen ValidationError werfen
        self.assertIsNone(log.display_duration_actual)

    def test_display_duration_must_be_integer(self):
        log = DisplayLogFactory()
        log.display_duration_actual = "not-an-int"
        with self.assertRaises(ValidationError):
            log.full_clean()

    def test_cascade_delete_message(self):
        log_pk = self.displayLog.pk
        self.displayLog.message.delete()
        # Der Log muss jetzt weg sein -> DoesNotExist
        with self.assertRaises(DisplayLog.DoesNotExist):
            DisplayLog.objects.get(pk=log_pk)

    def test_cascade_delete_device(self):
        log_pk = self.displayLog.pk
        self.displayLog.device.delete()
        with self.assertRaises(DisplayLog.DoesNotExist):
            DisplayLog.objects.get(pk=log_pk)

    def test_related_name_access(self):
        log2 = DisplayLogFactory(message=self.displayLog.message)
        logs = self.displayLog.message.display_logs.all()
        self.assertEqual(logs.count(), 2)
        self.assertIn(self.displayLog, logs)
        self.assertIn(log2, logs)
