from django.test import TestCase

from core.models import SyncLock
from core.sync_lock import SyncAlreadyRunningError, sync_lock


class SyncLockTest(TestCase):
    def test_rejects_overlapping_run_and_releases_afterwards(self):
        with (
            sync_lock("events"),
            self.assertRaises(SyncAlreadyRunningError),
            sync_lock("events"),
        ):
            pass
        lock = SyncLock.objects.get(name="events")
        assert lock.locked_until is None
