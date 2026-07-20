from core.sync_lock import SyncAlreadyRunningError, sync_lock
from django.core.management.base import BaseCommand, CommandError

from participants.reg_sync import RegSyncError, sync_due_participants


class Command(BaseCommand):
    help = "Synchronize due participant check-in states from registration API."

    def add_arguments(self, parser):
        parser.add_argument("--workers", type=int, default=8)

    def handle(self, *args, **options):  # noqa: ARG002
        try:
            with sync_lock("registration-sync"):
                synced, changed, failed = sync_due_participants(
                    workers=options["workers"]
                )
        except (RegSyncError, SyncAlreadyRunningError) as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                "Registration sync completed. "
                f"synced={synced}, changed={changed}, failed={failed}"
            )
        )
