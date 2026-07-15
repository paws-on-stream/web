from django.test import TestCase

from core.factories import DisplayDeviceFactory


class DeviceListActionHardeningTest(TestCase):
    def setUp(self):
        self.device = DisplayDeviceFactory()

    def test_rejects_unknown_action(self):
        response = self.client.post(
            "/core/devices/",
            {"action": "unknown", "select": [self.device.id]},
        )
        assert response.status_code == 400

    def test_rejects_missing_selection(self):
        response = self.client.post(
            "/core/devices/",
            {"action": "activate"},
        )
        assert response.status_code == 400
