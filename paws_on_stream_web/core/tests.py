from django.test import TestCase
from core.models import Settings
from django.core.exceptions import ValidationError

# Create your tests here.

class SettingsModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.settings = Settings.objects.create(id=1)

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


