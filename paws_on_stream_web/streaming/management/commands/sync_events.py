from core.sync_lock import SyncAlreadyRunningError, sync_lock
from django.core.management.base import BaseCommand, CommandError

from streaming.event_sync import EventSyncError, sync_events


class Command(BaseCommand):
    help = "Synchronize events from the configured external Event API."

    def handle(self, *args, **options):  # noqa: ARG002
        try:
            with sync_lock("event-sync"):
                summary = sync_events()
        except (EventSyncError, SyncAlreadyRunningError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(
                "Event sync completed. "
                f"received={summary.received}, created={summary.created}, "
                f"updated={summary.updated}, skipped={summary.skipped}"
            )
        )
