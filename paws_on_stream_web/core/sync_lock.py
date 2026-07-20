import uuid
from contextlib import contextmanager
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from core.models import SyncLock


class SyncAlreadyRunningError(RuntimeError):
    pass


@contextmanager
def sync_lock(name: str, *, lease_seconds: int = 900):
    owner = uuid.uuid4().hex
    now = timezone.now()
    with transaction.atomic():
        lock, _ = SyncLock.objects.select_for_update().get_or_create(name=name)
        if lock.locked_until and lock.locked_until > now:
            raise SyncAlreadyRunningError(f"Sync '{name}' is already running.")
        lock.owner = owner
        lock.locked_until = now + timedelta(seconds=lease_seconds)
        lock.save(update_fields=["owner", "locked_until"])

    try:
        yield
    finally:
        with transaction.atomic():
            lock = SyncLock.objects.select_for_update().filter(name=name).first()
            if lock and lock.owner == owner:
                lock.owner = ""
                lock.locked_until = None
                lock.save(update_fields=["owner", "locked_until"])
