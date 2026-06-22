from datetime import UTC, datetime

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from core.factories import DisplayDeviceFactory, DisplayLogFactory, SettingsFactory
from core.models import DisplayDevice, Settings

TEST_TOKEN = "test-api-token"


@override_settings(API_AUTH_TOKEN=TEST_TOKEN)
class SettingsViewTest(APITestCase):
    def setUp(self):
        self.client.credentials(HTTP_X_API_TOKEN=TEST_TOKEN)
        self.settings = SettingsFactory()

    def test_retrieve_settings(self):
        response = self.client.get("/api/v1/settings/1/")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["rate_limit_per_minute"] == 10
        assert response.json()["bot_status"] == "online"
        assert response.json()["display_mode"] == "chat"

    def test_update_settings(self):
        data = {"rate_limit_per_minute": 20, "bot_status": "maintenance"}
        response = self.client.patch("/api/v1/settings/1/", data, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["rate_limit_per_minute"] == 20
        assert response.json()["bot_status"] == "maintenance"

    def test_partial_update(self):
        data = {"auto_approve": True}
        response = self.client.patch("/api/v1/settings/1/", data, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["auto_approve"] is True
        # Original values should be preserved
        assert response.json()["rate_limit_per_minute"] == 10

    def test_settings_auto_created(self):
        Settings.objects.all().delete()
        response = self.client.get("/api/v1/settings/1/")
        assert response.status_code == status.HTTP_200_OK
        assert Settings.objects.count() == 1


@override_settings(API_AUTH_TOKEN=TEST_TOKEN)
class DisplayDeviceListViewTest(APITestCase):
    def setUp(self):
        self.client.credentials(HTTP_X_API_TOKEN=TEST_TOKEN)
        self.devices = DisplayDeviceFactory.create_batch(3)

    def test_list_devices(self):
        response = self.client.get("/api/v1/devices/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()["results"]) == 3

    def test_device_data_structure(self):
        response = self.client.get("/api/v1/devices/")
        device = response.json()["results"][0]
        assert "id" in device
        assert "device_id" in device
        assert "hostname" in device
        assert "location" in device
        assert "is_active" in device
        assert "last_seen" in device


@override_settings(API_AUTH_TOKEN=TEST_TOKEN)
class DisplayDeviceCreateViewTest(APITestCase):
    def setUp(self):
        self.client.credentials(HTTP_X_API_TOKEN=TEST_TOKEN)

    def test_create_device(self):
        data = {
            "device_id": "pi-new-001",
            "hostname": "new-display.local",
            "location": "Main Hall",
        }
        response = self.client.post("/api/v1/devices/", data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["device_id"] == "pi-new-001"
        assert response.json()["hostname"] == "new-display.local"
        assert DisplayDevice.objects.filter(device_id="pi-new-001").exists()


@override_settings(API_AUTH_TOKEN=TEST_TOKEN)
class DisplayDeviceRegisterActionTest(APITestCase):
    def setUp(self):
        self.client.credentials(HTTP_X_API_TOKEN=TEST_TOKEN)

    def test_register_new_device(self):
        data = {
            "device_id": "register-test-001",
            "hostname": "registered.local",
            "location": "Lobby",
        }
        response = self.client.post("/api/v1/devices/register/", data, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["device_id"] == "register-test-001"
        assert response.json()["hostname"] == "registered.local"
        assert response.json()["last_seen"] is not None

    def test_register_update_existing_device(self):
        device = DisplayDeviceFactory(device_id="update-test")
        now = datetime.now(tz=UTC)
        device.last_seen = datetime(2020, 1, 1, tzinfo=UTC)
        device.save()
        data = {
            "device_id": "update-test",
            "hostname": "updated-hostname",
        }
        response = self.client.post("/api/v1/devices/register/", data, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["hostname"] == "updated-hostname"
        device.refresh_from_db()
        assert device.hostname == "updated-hostname"
        # last_seen should be updated
        assert device.last_seen > now

    def test_register_missing_device_id(self):
        data = {"hostname": "no-id.local"}
        response = self.client.post("/api/v1/devices/register/", data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@override_settings(API_AUTH_TOKEN=TEST_TOKEN)
class DisplayLogListViewTest(APITestCase):
    def setUp(self):
        self.client.credentials(HTTP_X_API_TOKEN=TEST_TOKEN)
        self.logs = DisplayLogFactory.create_batch(3)

    def test_list_logs(self):
        response = self.client.get("/api/v1/logs/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()["results"]) == 3

    def test_log_data_structure(self):
        response = self.client.get("/api/v1/logs/")
        log = response.json()["results"][0]
        assert "id" in log
        assert "message" in log
        assert "device" in log
        assert "displayed_at" in log
        assert "display_duration_actual" in log

    def test_logs_read_only(self):
        data = {"message": 1, "device": 1}
        response = self.client.post("/api/v1/logs/", data, format="json")
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
