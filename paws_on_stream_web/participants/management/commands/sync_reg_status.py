from django.core.management.base import BaseCommand, CommandError

from participants.reg_sync import RegSyncError, sync_due_participants


class Command(BaseCommand):
    help = "Synchronize due participant check-in states from registration API."

    def handle(self, *args, **options):  # noqa: ARG002
        try:
            synced, changed = sync_due_participants()
        except RegSyncError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Registration sync completed. synced={synced}, changed={changed}"
            )
        )
