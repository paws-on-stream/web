from django.contrib.auth import get_user_model
from django.test import TestCase

from core.factories import DisplayDeviceFactory, DisplayLogFactory, SettingsFactory
from core.models import TelegramAccess


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
                "web_display_theme": "east-readable",
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


class TelegramAccessUIViewsTest(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            "telegram:1", is_staff=True, is_superuser=True
        )
        self.admin_access = TelegramAccess.objects.create(
            telegram_id=1,
            label="Admin",
            is_active=True,
            is_admin=True,
            user=self.admin,
        )
        self.pending = TelegramAccess.objects.create(
            telegram_id=2,
            label="Pending User",
            is_active=False,
        )

    def test_admin_can_see_pending_requests(self):
        self.client.force_login(self.admin)
        response = self.client.get("/core/telegram-access/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pending User")
        self.assertContains(response, "Wartet auf Freigabe")

    def test_staff_cannot_manage_telegram_access(self):
        staff = get_user_model().objects.create_user("staff", is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get("/core/telegram-access/").status_code, 403)
        self.assertEqual(
            self.client.post(
                f"/core/telegram-access/{self.pending.pk}/edit/",
                {"label": "Changed", "role": "admin", "is_active": "on"},
            ).status_code,
            403,
        )

    def test_admin_can_activate_staff(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            f"/core/telegram-access/{self.pending.pk}/edit/",
            {"label": "Operator", "role": "staff", "is_active": "on"},
        )
        self.assertRedirects(response, "/core/telegram-access/")
        self.pending.refresh_from_db()
        self.assertTrue(self.pending.is_active)
        self.assertFalse(self.pending.is_admin)

    def test_admin_can_assign_admin_role(self):
        self.client.force_login(self.admin)
        self.client.post(
            f"/core/telegram-access/{self.pending.pk}/edit/",
            {"label": "Second Admin", "role": "admin", "is_active": "on"},
        )
        self.pending.refresh_from_db()
        self.assertTrue(self.pending.is_active)
        self.assertTrue(self.pending.is_admin)

    def test_admin_cannot_revoke_own_admin_access(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            f"/core/telegram-access/{self.admin_access.pk}/edit/",
            {"label": "Admin", "role": "staff", "is_active": "on"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "nicht entziehen")
        self.admin_access.refresh_from_db()
        self.assertTrue(self.admin_access.is_admin)
        self.assertTrue(self.admin_access.is_active)
