from django.conf import settings
from django.db import models


class Event(models.Model):
    """Represents a convention event/session."""

    name = models.CharField(max_length=128)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    is_active = models.BooleanField(default=False)
    allow_messages = models.BooleanField(default=True)
    display_mode = models.CharField(
        max_length=16,
        null=True,
        blank=True,
        help_text="chat or crawling. null = use global setting",
    )
    scroll_speed_px = models.IntegerField(
        null=True,
        blank=True,
        help_text="Pixels per frame in crawling mode. null = use global setting",
    )

    class Meta:
        ordering = ["-starts_at"]

    def __str__(self):
        return f"{self.name} ({self.starts_at.strftime('%Y-%m-%d %H:%M')})"


class Message(models.Model):
    """Represents a message sent by a participant."""

    MEDIA_TYPES = [
        ("text", "Text"),
        ("photo", "Photo"),
        ("gif", "GIF"),
        ("sticker", "Sticker"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("displayed", "Displayed"),
    ]

    REJECTION_REASONS = [
        ("no_event", "No active event"),
        ("unknown", "Unknown participant"),
        ("not_checkedin", "Not checked in"),
        ("banned", "Banned"),
        ("rate_limit", "Rate limited"),
        ("offline", "Bot offline"),
    ]

    participant = models.ForeignKey(
        "participants.Participant", on_delete=models.CASCADE, related_name="messages"
    )
    content = models.TextField(max_length=4096)
    raw_content = models.TextField(null=True, blank=True)
    media_type = models.CharField(
        max_length=16, choices=MEDIA_TYPES, null=True, blank=True
    )
    media_url = models.URLField(null=True, blank=True)
    sticker_emoji = models.CharField(max_length=64, null=True, blank=True)
    spam_score = models.IntegerField(default=0)
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default="pending"
    )
    rejection_reason = models.CharField(
        max_length=32, choices=REJECTION_REASONS, null=True, blank=True
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_messages",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    displayed_at = models.DateTimeField(null=True, blank=True)
    event = models.ForeignKey(
        Event, on_delete=models.SET_NULL, null=True, blank=True, related_name="messages"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["participant", "created_at"]),
        ]

    def __str__(self):
        return f"{self.participant.display_name}: {self.content[:50]}..."
