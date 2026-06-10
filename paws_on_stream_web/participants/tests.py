from django.core.exceptions import ValidationError
from django.test import TestCase

from participants.factories import ParticipantFactory
from participants.models import Participant

# Create your tests here.


class ParticipantsModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.participant = ParticipantFactory()

    def test_str_returns_human_readable(self):
        self.assertEqual(
            str(self.participant),
            f"{self.participant.display_name} (TG:{self.participant.telegram_id})",
        )

    def test_defaults_are_set(self):
        p = Participant.objects.get(telegram_id=self.participant.telegram_id)
        self.assertFalse(p.banned)
        self.assertFalse(p.checked_in)
        self.assertEqual(p.spam_count, 0)

    def test_empty_or_null_fields(self):
        p = Participant.objects.get(telegram_id=self.participant.telegram_id)
        p.reg_id = None
        p.last_status_check = None
        p.muted_until = None
        p.full_clean()

    def test_validation(self):
        p = Participant.objects.get(telegram_id=self.participant.telegram_id)
        p.last_status_check = "not-a-datetime"
        p.muted_until = "not-a-datetime"
        p.spam_count = "not-a-int"
        p.reg_id = "not-a-int"
        with self.assertRaises(ValidationError):
            p.full_clean()
