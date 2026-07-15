from django.test import RequestFactory, TestCase

from streaming.factories import EventFactory, TextMessageFactory
from streaming.tables import EventTable, MessageTable


class MessageTableTest(TestCase):
    def setUp(self):
        self.request = RequestFactory().get("/")
        self.message = TextMessageFactory(
            content="Hello from the table view",
            media_type="text",
            status="approved",
        )

    def test_renders_badges_and_links(self):
        html = MessageTable([self.message]).as_html(self.request)
        assert "badge bg-success" in html
        assert self.message.participant.get_absolute_url() in html


class EventTableTest(TestCase):
    def setUp(self):
        self.request = RequestFactory().get("/")
        self.event = EventFactory(is_active=True, allow_messages=False)

    def test_renders_status_badges(self):
        html = EventTable([self.event]).as_html(self.request)
        assert "badge bg-success" in html
        assert "badge bg-danger" in html
        assert self.event.get_absolute_url() in html
