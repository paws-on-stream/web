from django.contrib.auth import get_user_model
from django.test import TestCase

from core.factories import DisplayDeviceFactory, DisplayLogFactory, SettingsFactory


class DisplayUIViewsTest(TestCase):
    def setUp(self):
        self.client.force_login(
            get_user_model().objects.create_user("staff", is_staff=True)
        )

    def test_settings_page_exposes_edit_link(self):
        SettingsFactory()
        response = self.client.get("/core/settings/")
        assert response.status_code == 200
        assert "/core/settings/edit/" in response.content.decode()

    def test_settings_edit_page_renders(self):
        SettingsFactory()
        response = self.client.get("/core/settings/edit/")
        assert response.status_code == 200
        assert "Edit Settings" in response.content.decode()

    def test_settings_edit_uses_readable_sections_and_display_mode_select(self):
        SettingsFactory()
        response = self.client.get("/core/settings/edit/")
        content = response.content.decode()
        assert response.status_code == 200
        assert "Bot und Moderation" in content
        assert "Registrierungssystem" in content
        assert '<select name="display_mode"' in content
        assert ">Chat</option>" in content
        assert ">Crawling</option>" in content

    def test_settings_edit_persists_event_api_and_jq_filter(self):
        settings = SettingsFactory()
        jq_filter = '[.[] | select(.attributes | type == "object" and has("live"))]'
        response = self.client.post(
            "/core/settings/edit/",
            {
                "rate_limit_per_minute": 10,
                "max_message_length": 4096,
                "spam_threshold": 5,
                "bot_status": "online",
                "overlay_theme": "default",
                "overlay_font_size": 24,
                "display_duration_sec": 8,
                "display_mode": "chat",
                "scroll_speed_px": 3,
                "reg_api_url": "",
                "reg_api_key": "",
                "status_check_interval": 300,
                "event_api_url": "https://sigma.example/api/events?signature=secret",
                "event_api_jsonq_filter": jq_filter,
                "require_event_active": "on",
            },
        )
        assert response.status_code == 302
        settings.refresh_from_db()
        assert settings.event_api_jsonq_filter == jq_filter

    def test_device_detail_renders_existing_template(self):
        device = DisplayDeviceFactory()
        response = self.client.get(f"/core/devices/{device.pk}/")
        assert response.status_code == 200
        template_names = [
            template.name for template in response.templates if template.name
        ]
        assert "core/device_detail.html" in template_names

    def test_device_edit_page_renders(self):
        device = DisplayDeviceFactory()
        response = self.client.get(f"/core/devices/{device.pk}/edit/")
        assert response.status_code == 200
        template_names = [
            template.name for template in response.templates if template.name
        ]
        assert "core/device_form.html" in template_names

    def test_display_log_list_is_visible(self):
        log = DisplayLogFactory()
        response = self.client.get("/core/logs/")
        assert response.status_code == 200
        assert "Display Logs" in response.content.decode()
        assert log.device.device_id in response.content.decode()
