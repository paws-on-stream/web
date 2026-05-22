from django.db import models


class Participant(models.Model):
    """Represents a convention participant who can send messages."""

    telegram_id = models.BigIntegerField(unique=True)
    reg_id = models.IntegerField(null=True, blank=True)
    display_name = models.CharField(max_length=128)
    checked_in = models.BooleanField(default=False)
    last_status_check = models.DateTimeField(null=True, blank=True)
    banned = models.BooleanField(default=False)
    muted_until = models.DateTimeField(null=True, blank=True)
    spam_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.display_name} (TG:{self.telegram_id})"
