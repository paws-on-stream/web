from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from participants.factories import ParticipantFactory
from participants.models import Participant


class ParticipantDetailActionTest(TestCase):
    def setUp(self):
        self.client.force_login(
            get_user_model().objects.create_user("staff", is_staff=True)
        )
        self.participant = ParticipantFactory()
        self.url = f"/participants/participants/{self.participant.pk}/"

    def test_ban_action(self):
        response = self.client.post(self.url, {"action": "ban"})
        assert response.status_code == 302
        self.participant.refresh_from_db()
        assert self.participant.banned is True

    def test_unban_action_clears_mute(self):
        self.participant.banned = True
        self.participant.muted_until = timezone.now()
        self.participant.save(update_fields=["banned", "muted_until"])

        response = self.client.post(self.url, {"action": "unban"})
        assert response.status_code == 302
        self.participant.refresh_from_db()
        assert self.participant.banned is False
        assert self.participant.muted_until is None

    def test_mute_action(self):
        response = self.client.post(self.url, {"action": "mute", "minutes": "20"})
        assert response.status_code == 302
        self.participant.refresh_from_db()
        assert self.participant.muted_until is not None
        assert self.participant.muted_until > timezone.now()

    def test_unmute_action(self):
        self.participant.muted_until = timezone.now()
        self.participant.save(update_fields=["muted_until"])

        response = self.client.post(self.url, {"action": "unmute"})
        assert response.status_code == 302
        self.participant.refresh_from_db()
        assert self.participant.muted_until is None

    def test_mute_action_invalid_minutes(self):
        response = self.client.post(self.url, {"action": "mute", "minutes": "nope"})
        assert response.status_code == 400

    def test_delete_action(self):
        response = self.client.post(self.url, {"action": "delete"})
        assert response.status_code == 302
        assert not Participant.objects.filter(pk=self.participant.pk).exists()

    def test_unknown_action_returns_400(self):
        response = self.client.post(self.url, {"action": "surprise"})
        assert response.status_code == 400

    def test_detail_shows_mute_button_when_not_muted(self):
        response = self.client.get(self.url)
        assert response.status_code == 200
        content = response.content.decode()
        assert 'value="mute"' in content
        assert 'value="unmute"' not in content

    def test_detail_shows_unmute_button_when_muted(self):
        self.participant.muted_until = timezone.now() + timedelta(minutes=10)
        self.participant.save(update_fields=["muted_until"])

        response = self.client.get(self.url)
        assert response.status_code == 200
        content = response.content.decode()
        assert 'value="unmute"' in content
        assert 'value="mute"' not in content
