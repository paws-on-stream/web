from django.db import models


class Settings(models.Model):
    """Global application settings (singleton)."""

    BOT_STATUSES = [
        ("online", "Online"),
        ("offline", "Offline"),
        ("maintenance", "Maintenance"),
    ]

    rate_limit_per_minute = models.IntegerField(default=10)
    max_message_length = models.IntegerField(default=4096)
    bot_status = models.CharField(
        max_length=16, choices=BOT_STATUSES, default="online"
    )
    overlay_theme = models.CharField(max_length=32, default="default")
    overlay_font_size = models.IntegerField(default=24)
    auto_approve = models.BooleanField(default=False)
    display_duration_sec = models.IntegerField(default=8)
    reg_api_url = models.URLField(blank=True)
    reg_api_key = models.CharField(max_length=128, blank=True)
    status_check_interval = models.IntegerField(default=300)
    require_event_active = models.BooleanField(default=True)
    display_mode = models.CharField(max_length=16, default="chat")
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
    location = models.CharField(max_length=64, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    last_seen = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["device_id"]

    def __str__(self):
        return f"{self.device_id} ({self.hostname})"


class DisplayLog(models.Model):
    """Logs when a message was displayed on which device."""

    message = models.ForeignKey(
        "messages.Message", on_delete=models.CASCADE, related_name="display_logs"
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
