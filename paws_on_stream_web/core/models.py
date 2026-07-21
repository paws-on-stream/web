import hashlib
import secrets
import uuid
from hmac import compare_digest

from django.conf import settings
from django.db import models
from django.urls import reverse


class Settings(models.Model):
    """Global application settings (singleton)."""

    BOT_STATUSES = [
        ("online", "Online"),
        ("offline", "Offline"),
        ("maintenance", "Maintenance"),
    ]
    DISPLAY_MODES = [
        ("chat", "Chat"),
        ("crawling", "Crawling"),
    ]
    WEB_DISPLAY_THEMES = [("east-readable", "EAST Readable")]

    rate_limit_per_minute = models.IntegerField(default=10)
    max_message_length = models.IntegerField(default=4096)
    bot_status = models.CharField(max_length=16, choices=BOT_STATUSES, default="online")
    overlay_theme = models.CharField(max_length=32, default="default")
    web_display_theme = models.CharField(
        max_length=32,
        choices=WEB_DISPLAY_THEMES,
        default="east-readable",
    )
    overlay_font_size = models.IntegerField(default=24)
    auto_approve = models.BooleanField(default=False)
    spam_threshold = models.PositiveIntegerField(default=5)
    display_duration_sec = models.IntegerField(default=8)
    reg_api_url = models.URLField(blank=True)
    reg_api_key = models.CharField(max_length=128, blank=True)
    event_api_url = models.URLField(blank=True)
    event_api_jsonq_filter = models.TextField(
        blank=True,
        default="",
        help_text="jq filter applied to the event API response.",
    )
    status_check_interval = models.IntegerField(default=300)
    require_event_active = models.BooleanField(default=True)
    display_mode = models.CharField(
        max_length=16, choices=DISPLAY_MODES, default="chat"
    )
    scroll_speed_px = models.IntegerField(default=3)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Setting"
        verbose_name_plural = "Settings"

    def __str__(self):
        return "Application Settings"

    @classmethod
    def get_settings(cls):
        """Get or create the singleton settings instance."""
        settings, created = cls.objects.get_or_create(id=1)
        return settings


class DisplayDevice(models.Model):
    """Represents a Raspberry Pi display device."""

    device_id = models.CharField(max_length=32, unique=True)
    hostname = models.CharField(max_length=128)
    location = models.CharField(max_length=64, default="", blank=True)
    is_active = models.BooleanField(default=True)
    last_seen = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["device_id"]

    def __str__(self):
        return f"{self.hostname} ({self.device_id})"

    def get_absolute_url(self):
        return reverse("core:device_detail", kwargs={"pk": self.pk})


class DisplayLog(models.Model):
    """Logs when a message was displayed on which device."""

    message = models.ForeignKey(
        "streaming.Message", on_delete=models.CASCADE, related_name="display_logs"
    )
    device = models.ForeignKey(
        DisplayDevice, on_delete=models.CASCADE, related_name="display_logs"
    )
    displayed_at = models.DateTimeField(auto_now_add=True)
    display_duration_actual = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-displayed_at"]
        indexes = [
            models.Index(fields=["message", "displayed_at"]),
            models.Index(fields=["device", "displayed_at"]),
        ]

    def __str__(self):
        return (
            f"{self.message.participant.display_name} on "
            f"{self.device.device_id} at {self.displayed_at}"
        )


class SyncLock(models.Model):
    """Database-backed lease preventing overlapping scheduled sync runs."""

    name = models.CharField(max_length=64, unique=True)
    locked_until = models.DateTimeField(null=True, blank=True)
    owner = models.CharField(max_length=64, blank=True, default="")

    def __str__(self):
        return self.name


class TelegramAccess(models.Model):
    """Allow-list entry and local identity for a Telegram dashboard user."""

    telegram_id = models.BigIntegerField(unique=True)
    label = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="telegram_access",
    )
    last_login_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("label", "telegram_id")
        verbose_name = "Telegram access"
        verbose_name_plural = "Telegram access"

    def __str__(self):
        return self.label or str(self.telegram_id)


class WebDisplayAccess(models.Model):
    """Singleton credential state for the public passive web display."""

    token_digest = models.CharField(max_length=64, blank=True)
    generation = models.UUIDField(default=uuid.uuid4, editable=False)
    is_active = models.BooleanField(default=False)
    rotated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "Active web display link" if self.is_active else "No web display link"

    @classmethod
    def get_access(cls):
        access, _ = cls.objects.get_or_create(pk=1)
        return access

    def rotate(self):
        token = secrets.token_urlsafe(32)
        self.token_digest = hashlib.sha256(token.encode()).hexdigest()
        self.generation = uuid.uuid4()
        self.is_active = True
        self.save()
        return token

    def revoke(self):
        self.token_digest = ""
        self.generation = uuid.uuid4()
        self.is_active = False
        self.save()

    def accepts(self, token):
        if not self.is_active or not self.token_digest or not token:
            return False
        digest = hashlib.sha256(str(token).encode()).hexdigest()
        return compare_digest(self.token_digest, digest)
