import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse


class MediaAsset(models.Model):
    """Persisted media uploaded by the bot."""

    MEDIA_TYPES = [
        ("photo", "Photo"),
        ("gif", "GIF"),
        ("sticker", "Sticker"),
    ]

    file = models.FileField(upload_to="media_assets/%Y/%m/")
    media_type = models.CharField(max_length=16, choices=MEDIA_TYPES)
    telegram_file_id = models.CharField(max_length=255)
    telegram_file_unique_id = models.CharField(max_length=255, unique=True, blank=True)
    sticker_emoji = models.CharField(max_length=64, blank=True, default="")
    source_filename = models.CharField(max_length=255, blank=True, default="")
    format = models.CharField(max_length=16, default="webp", editable=False)
    animated = models.BooleanField(default=False)
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    duration_ms = models.PositiveIntegerField(default=0)
    frame_count = models.PositiveIntegerField(default=1)
    has_alpha = models.BooleanField(default=False)
    sha256 = models.CharField(max_length=64, db_index=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["media_type", "created_at"]),
        ]

    def __str__(self):
        identifier = self.telegram_file_unique_id or self.telegram_file_id
        return f"{self.media_type}:{identifier}"

    def get_absolute_url(self):
        return self.file.url


class Event(models.Model):
    """Represents a convention event/session."""

    DISPLAY_MODES = [
        ("", "Global setting"),
        ("chat", "Chat"),
        ("crawling", "Crawling"),
    ]

    name = models.CharField(max_length=128)
    external_id = models.CharField(max_length=64, unique=True, null=True, blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    is_active = models.BooleanField(default=False)
    allow_messages = models.BooleanField(default=True)
    display_mode = models.CharField(
        max_length=16,
        choices=DISPLAY_MODES,
        default="",
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
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(fields=["starts_at", "ends_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["is_active"],
                condition=Q(is_active=True),
                name="streaming_single_active_event",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.starts_at.strftime('%Y-%m-%d %H:%M')})"

    def get_absolute_url(self):
        return reverse("streaming:event_detail", kwargs={"pk": self.pk})

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "End time must be after start time."})
        super().clean()


class DisplayEvent(models.Model):
    """Persistent operational event reported by a display client."""

    EVENT_TYPES = [
        ("killswitch", "Killswitch"),
        ("pause", "Pause"),
        ("resume", "Resume"),
        ("clear", "Clear"),
    ]

    device = models.ForeignKey(
        "core.DisplayDevice", on_delete=models.CASCADE, related_name="events"
    )
    event_type = models.CharField(max_length=16, choices=EVENT_TYPES)
    occurred_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [models.Index(fields=["device", "occurred_at"])]

    def __str__(self):
        return f"{self.device.device_id}:{self.event_type}@{self.occurred_at}"


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
    ]

    REJECTION_REASONS = [
        ("no_event", "No active event"),
        ("unknown", "Unknown participant"),
        ("not_checkedin", "Not checked in"),
        ("banned", "Banned"),
        ("rate_limit", "Rate limited"),
        ("offline", "Bot offline"),
        ("spam", "Spam"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    participant = models.ForeignKey(
        "participants.Participant", on_delete=models.CASCADE, related_name="messages"
    )
    content = models.TextField(max_length=4096)
    raw_content = models.TextField(default="", blank=True)
    media_type = models.CharField(
        max_length=16, choices=MEDIA_TYPES, default="", blank=True
    )
    media_url = models.URLField(default="", blank=True)
    media_asset = models.ForeignKey(
        MediaAsset,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="messages",
    )
    sticker_emoji = models.CharField(max_length=64, default="", blank=True)
    spam_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="pending")
    rejection_reason = models.CharField(
        max_length=32, choices=REJECTION_REASONS, default="", blank=True
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

    def get_absolute_url(self):
        return reverse("streaming:message_detail", kwargs={"pk": self.pk})
