from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from streaming.factories import TextMessageFactory
from streaming.models import Message


class CleanupCommandTest(TestCase):
    def setUp(self):
        self.old = TextMessageFactory()
        Message.objects.filter(pk=self.old.pk).update(
            created_at=timezone.now() - timedelta(days=31)
        )

    def test_dry_run_is_default(self):
        output = StringIO()
        call_command("cleanup_old_data", stdout=output)
        assert Message.objects.filter(pk=self.old.pk).exists()
        assert "would_delete" in output.getvalue()

    def test_execute_removes_old_messages(self):
        call_command("cleanup_old_data", execute=True, stdout=StringIO())
        assert not Message.objects.filter(pk=self.old.pk).exists()
