from rest_framework import serializers

from core.models import DisplayDevice, DisplayLog, Settings


class SettingsSerializer(serializers.ModelSerializer):
    """Serializer for Settings model."""

    class Meta:
        model = Settings
        fields = [
            "id",
            "rate_limit_per_minute",
            "max_message_length",
            "bot_status",
            "overlay_theme",
            "overlay_font_size",
            "auto_approve",
            "display_duration_sec",
            "reg_api_url",
            "reg_api_key",
            "status_check_interval",
            "require_event_active",
            "display_mode",
            "scroll_speed_px",
            "updated_at",
        ]
        read_only_fields = ["id", "updated_at"]


class DisplayDeviceSerializer(serializers.ModelSerializer):
    """Serializer for DisplayDevice model."""

    class Meta:
        model = DisplayDevice
        fields = ["id", "device_id", "hostname", "location", "is_active", "last_seen"]
        read_only_fields = ["id"]


class DisplayLogSerializer(serializers.ModelSerializer):
    """Serializer for DisplayLog model."""

    class Meta:
        model = DisplayLog
        fields = [
            "id",
            "message",
            "device",
            "displayed_at",
            "display_duration_actual",
        ]
        read_only_fields = ["id", "displayed_at"]
