from datetime import timedelta
from io import StringIO
from unittest.mock import patch
from urllib.error import HTTPError

from core.factories import SettingsFactory
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from participants.factories import ParticipantFactory
from participants.models import Participant
from participants.reg_sync import (
    RegParticipantNotFound,
    RegSyncError,
    fetch_reg_status,
    parse_reg_status,
    sync_due_participants,
    sync_participant_by_telegram_id,
)


class RegSyncParseTest(TestCase):
    def test_parse_east_payload(self):
        status = parse_reg_status(
            {
                "success": True,
                "reg_id": 1,
                "nickname": "FurryName",
                "payment_status": "paid",
                "checkedin": False,
            }
        )
        assert status.checked_in is False
        assert status.reg_id == 1
        assert status.display_name == "FurryName"

    def test_parse_east_unknown_participant(self):
        with self.assertRaisesMessage(RegParticipantNotFound, "invalid telegram id"):
            parse_reg_status({"error": True, "msg": "invalid telegram id"})

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


class RegSyncRequestTest(TestCase):
    def setUp(self):
        SettingsFactory(
            reg_api_url="https://east.sachsenfurs.de/?page=TelegramInfo",
            reg_api_key="secret key",
        )

    @patch("participants.reg_sync.validate_public_https_url")
    @patch("participants.reg_sync.urlopen")
    def test_uses_east_query_contract(self, mock_urlopen, _mock_validate_url):
        response = mock_urlopen.return_value.__enter__.return_value
        response.read.return_value = (
            b'{"success":true,"reg_id":1,"nickname":"Paws","checkedin":true}'
        )

        status = fetch_reg_status(82939949)

        request = mock_urlopen.call_args.args[0]
        assert request.full_url == (
            "https://east.sachsenfurs.de/"
            "?page=TelegramInfo&tg_user_id=82939949&key=secret+key"
        )
        assert request.get_header("X-api-token") is None
        assert status.display_name == "Paws"
        assert status.checked_in is True

    @patch("participants.reg_sync.validate_public_https_url")
    @patch("participants.reg_sync.urlopen")
    def test_http_404_is_unknown_participant(self, mock_urlopen, _mock_validate_url):
        mock_urlopen.side_effect = HTTPError(
            "https://east.sachsenfurs.de/", 404, "Not Found", {}, None
        )
        with self.assertRaises(RegParticipantNotFound):
            fetch_reg_status(82939949)


class RegSyncDueParticipantsTest(TestCase):
    def setUp(self):
        SettingsFactory(
            status_check_interval=300, reg_api_url="https://reg.example/api"
        )

    @patch("participants.reg_sync.fetch_reg_status")
    def test_syncs_only_due_participants(self, mock_fetch):
        due_participant = ParticipantFactory(last_status_check=None, checked_in=False)
        recent_participant = ParticipantFactory(
            last_status_check=timezone.now(),
            checked_in=False,
        )
        mock_fetch.return_value = parse_reg_status({"checked_in": True, "reg_id": 55})

        synced, changed, failed = sync_due_participants()

        assert synced == 1
        assert changed == 1
        assert failed == 0
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

        synced, changed, failed = sync_due_participants()

        assert synced == 1
        assert changed == 0
        assert failed == 0

    @patch("participants.reg_sync.fetch_reg_status")
    def test_sync_updates_raw_status_without_removing_override(self, mock_fetch):
        participant = ParticipantFactory(
            last_status_check=None,
            checked_in=False,
            checked_in_override=False,
        )
        mock_fetch.return_value = parse_reg_status(
            {"checked_in": True, "reg_id": participant.reg_id}
        )

        sync_due_participants()

        participant.refresh_from_db()
        assert participant.checked_in is True
        assert participant.checked_in_override is False
        assert participant.effective_checked_in is False

    @patch("participants.reg_sync.fetch_reg_status")
    def test_one_failure_does_not_abort_remaining_participants(self, mock_fetch):
        ParticipantFactory(last_status_check=None)
        ParticipantFactory(last_status_check=None)
        mock_fetch.side_effect = [
            RegSyncError("temporary failure"),
            parse_reg_status({"checked_in": True, "reg_id": 23}),
        ]

        synced, changed, failed = sync_due_participants()

        assert synced == 1
        assert changed == 1
        assert failed == 1


class RegSyncUpsertTest(TestCase):
    @patch("participants.reg_sync.fetch_reg_status")
    def test_creates_unknown_participant_from_registration_data(self, mock_fetch):
        mock_fetch.return_value = parse_reg_status(
            {
                "checked_in": True,
                "reg_id": 73,
                "display_name": "New Attendee",
            }
        )

        participant, changed, created = sync_participant_by_telegram_id(987654321)

        assert created is True
        assert changed is True
        assert participant.checked_in is True
        assert participant.reg_id == 73
        assert Participant.objects.filter(telegram_id=987654321).exists()

    @patch("participants.reg_sync.fetch_reg_status")
    def test_refuses_new_participant_without_display_name(self, mock_fetch):
        mock_fetch.return_value = parse_reg_status({"checked_in": True, "reg_id": 73})
        with self.assertRaisesMessage(RegSyncError, "display_name"):
            sync_participant_by_telegram_id(987654321)


class SyncRegStatusCommandTest(TestCase):
    @patch("participants.management.commands.sync_reg_status.sync_due_participants")
    def test_command_prints_summary(self, mock_sync_due):
        mock_sync_due.return_value = (3, 2, 1)
        out = StringIO()

        call_command("sync_reg_status", stdout=out)

        assert "synced=3, changed=2" in out.getvalue()
        assert "failed=1" in out.getvalue()

    @patch("participants.management.commands.sync_reg_status.sync_due_participants")
    def test_command_raises_on_sync_error(self, mock_sync_due):
        mock_sync_due.side_effect = RegSyncError("Registration API is unreachable.")

        with self.assertRaisesMessage(CommandError, "Registration API is unreachable."):
            call_command("sync_reg_status")
