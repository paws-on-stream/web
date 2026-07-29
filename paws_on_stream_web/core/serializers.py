from rest_framework import serializers

from core.models import DisplayDevice, DisplayLog, Settings
from core.themes import available_theme_choices


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
            "spam_threshold",
            "display_duration_sec",
            "reg_api_url",
            "reg_api_key",
            "event_api_url",
            "event_api_jsonq_filter",
            "status_check_interval",
            "require_event_active",
            "display_mode",
            "scroll_speed_px",
            "theme_reload_generation",
            "updated_at",
        ]
        read_only_fields = ["id", "updated_at"]
        extra_kwargs = {
            "reg_api_key": {"write_only": True},
            "reg_api_url": {"write_only": True},
            "event_api_url": {"write_only": True},
            "event_api_jsonq_filter": {"write_only": True},
        }

    def validate_overlay_theme(self, value):
        if value not in dict(available_theme_choices()):
            raise serializers.ValidationError("Unknown display theme.")
        return value


class DisplayDeviceSerializer(serializers.ModelSerializer):
    """Serializer for DisplayDevice model."""

    class Meta:
        model = DisplayDevice
        fields = [
            "id", "device_id", "hostname", "location", "is_active", "last_seen",
            "theme_cache_theme", "theme_cache_version", "theme_reload_generation",
            "theme_cache_updated_at",
        ]
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
