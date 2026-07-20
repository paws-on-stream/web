from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from streaming.models import MediaAsset, Message


class Command(BaseCommand):
    help = (
        "Remove old messages and unreferenced media. Dry-run unless --execute is set."
    )

    def add_arguments(self, parser):
        parser.add_argument("--message-days", type=int, default=30)
        parser.add_argument("--media-days", type=int, default=7)
        parser.add_argument("--execute", action="store_true")

    def handle(self, *args, **options):  # noqa: ARG002
        now = timezone.now()
        messages = Message.objects.filter(
            created_at__lt=now - timedelta(days=max(options["message_days"], 1))
        )
        media = MediaAsset.objects.filter(
            messages__isnull=True,
            created_at__lt=now - timedelta(days=max(options["media_days"], 1)),
        )
        message_count = messages.count()
        media_count = media.count()
        if options["execute"]:
            messages.delete()
            for asset in media.iterator():
                asset.file.delete(save=False)
                asset.delete()
        mode = "deleted" if options["execute"] else "would_delete"
        self.stdout.write(
            f"Cleanup {mode}. messages={message_count}, media_assets={media_count}"
        )
