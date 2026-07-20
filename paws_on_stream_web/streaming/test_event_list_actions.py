from django.contrib.auth import get_user_model
from django.test import TestCase

from streaming.factories import EventFactory


class EventListActionTest(TestCase):
    def setUp(self):
        self.client.force_login(
            get_user_model().objects.create_user("staff", is_staff=True)
        )
        self.url = "/streaming/events/"

    def test_bulk_action_without_selection_redirects_instead_of_400(self):
        response = self.client.post(self.url, {"action": "activate"})
        assert response.status_code == 302
        assert response.headers["Location"].endswith(self.url)

    def test_bulk_activate_selected_events(self):
        active_event = EventFactory(is_active=False)
        response = self.client.post(
            self.url,
            {"action": "activate", "select": [str(active_event.pk)]},
        )
        assert response.status_code == 302
        active_event.refresh_from_db()
        assert active_event.is_active is True
