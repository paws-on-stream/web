from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from streaming.factories import EventFactory
from streaming.models import Event


class EventManagementViewTest(TestCase):
    def setUp(self):
        self.client.force_login(
            get_user_model().objects.create_user("staff", is_staff=True)
        )

    def test_event_create_page_renders(self):
        response = self.client.get("/streaming/events/new/")
        assert response.status_code == 200
        assert "New Event" in response.content.decode()

    def test_event_create_flow(self):
        starts_at = timezone.now() + timedelta(hours=1)
        ends_at = starts_at + timedelta(hours=2)

        response = self.client.post(
            "/streaming/events/new/",
            {
                "name": "Ad-hoc Panel",
                "starts_at": starts_at.strftime("%Y-%m-%d %H:%M:%S"),
                "ends_at": ends_at.strftime("%Y-%m-%d %H:%M:%S"),
                "allow_messages": "on",
            },
        )

        assert response.status_code == 302
        assert response.url == "/streaming/events/"
        assert Event.objects.filter(name="Ad-hoc Panel").exists()

    def test_event_detail_activate_action(self):
        event = EventFactory(is_active=False)

        response = self.client.post(
            f"/streaming/events/{event.pk}/",
            {"action": "activate"},
        )

        assert response.status_code == 200
        event.refresh_from_db()
        assert event.is_active is True

    def test_event_detail_deactivate_action(self):
        event = EventFactory(is_active=True)

        response = self.client.post(
            f"/streaming/events/{event.pk}/",
            {"action": "deactivate"},
        )

        assert response.status_code == 200
        event.refresh_from_db()
        assert event.is_active is False

    def test_event_detail_invalid_action(self):
        event = EventFactory(is_active=True)

        response = self.client.post(
            f"/streaming/events/{event.pk}/",
            {"action": "nope"},
        )

        assert response.status_code == 400
