from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from core.factories import SettingsFactory
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from participants.factories import ParticipantFactory
from participants.reg_sync import RegSyncError, parse_reg_status, sync_due_participants


class RegSyncParseTest(TestCase):
    def test_parse_checked_in_payload(self):
        status = parse_reg_status({"checked_in": True, "reg_id": 42})
        assert status.checked_in is True
        assert status.reg_id == 42

    def test_parse_status_string_payload(self):
        status = parse_reg_status({"participant": {"status": "checked_in", "id": 7}})
        assert status.checked_in is True
        assert status.reg_id == 7

    def test_parse_raises_on_invalid_payload(self):
        with self.assertRaises(RegSyncError):
            parse_reg_status({"reg_id": 12})


class RegSyncDueParticipantsTest(TestCase):
    def setUp(self):
        SettingsFactory(status_check_interval=300, reg_api_url="https://reg.example/api")

    @patch("participants.reg_sync.fetch_reg_status")
    def test_syncs_only_due_participants(self, mock_fetch):
        due_participant = ParticipantFactory(last_status_check=None, checked_in=False)
        recent_participant = ParticipantFactory(
            last_status_check=timezone.now(),
            checked_in=False,
        )
        mock_fetch.return_value = parse_reg_status({"checked_in": True, "reg_id": 55})

        synced, changed = sync_due_participants()

        assert synced == 1
        assert changed == 1
        due_participant.refresh_from_db()
        recent_participant.refresh_from_db()
        assert due_participant.checked_in is True
        assert due_participant.reg_id == 55
        assert recent_participant.checked_in is False

    @patch("participants.reg_sync.fetch_reg_status")
    def test_syncs_when_last_check_is_older_than_interval(self, mock_fetch):
        ParticipantFactory(
            last_status_check=timezone.now() - timedelta(minutes=10),
            checked_in=False,
        )
        mock_fetch.return_value = parse_reg_status(
            {"checked_in": False, "reg_id": None}
        )

        synced, changed = sync_due_participants()

        assert synced == 1
        assert changed == 0


class SyncRegStatusCommandTest(TestCase):
    @patch("participants.management.commands.sync_reg_status.sync_due_participants")
    def test_command_prints_summary(self, mock_sync_due):
        mock_sync_due.return_value = (3, 2)
        out = StringIO()

        call_command("sync_reg_status", stdout=out)

        assert "synced=3, changed=2" in out.getvalue()

    @patch("participants.management.commands.sync_reg_status.sync_due_participants")
    def test_command_raises_on_sync_error(self, mock_sync_due):
        mock_sync_due.side_effect = RegSyncError("Registration API is unreachable.")

        with self.assertRaisesMessage(CommandError, "Registration API is unreachable."):
            call_command("sync_reg_status")
