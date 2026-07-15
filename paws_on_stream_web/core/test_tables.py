from django.test import RequestFactory, TestCase

from core.factories import DisplayDeviceFactory
from core.tables import DisplayDeviceTable


class DisplayDeviceTableTest(TestCase):
    def setUp(self):
        self.request = RequestFactory().get("/")
        self.device = DisplayDeviceFactory(
            device_id="pi-001",
            hostname="pi-001.local",
            is_active=True,
        )

    def test_renders_badges_and_links(self):
        html = DisplayDeviceTable([self.device]).as_html(self.request)
        assert "badge bg-success" in html
        assert "<code>pi-001</code>" in html
        assert self.device.get_absolute_url() in html
