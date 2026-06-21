from rest_framework import serializers

from streaming.models import Event, Message


class EventSerializer(serializers.ModelSerializer):
    """Serializer for Event model."""

    class Meta:
        model = Event
        fields = [
            "id",
            "name",
            "starts_at",
            "ends_at",
            "is_active",
            "allow_messages",
            "display_mode",
            "scroll_speed_px",
        ]
        read_only_fields = ["id"]


class ParticipantSummarySerializer(serializers.Serializer):
    """Compact participant reference for Message."""

    display_name = serializers.CharField()
    telegram_id = serializers.IntegerField()
    checked_in = serializers.BooleanField()


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for Message model."""

    participant = ParticipantSummarySerializer(read_only=True)
    participant_id = serializers.IntegerField(write_only=True)
    media_type_display = serializers.CharField(
        source="get_media_type_display", read_only=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    rejection_reason_display = serializers.CharField(
        source="get_rejection_reason_display", read_only=True
    )

    class Meta:
        model = Message
        fields = [
            "id",
            "participant",
            "participant_id",
            "content",
            "raw_content",
            "media_type",
            "media_type_display",
            "media_url",
            "sticker_emoji",
            "spam_score",
            "status",
            "status_display",
            "rejection_reason",
            "rejection_reason_display",
            "approved_by",
            "approved_at",
            "displayed_at",
            "event",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "approved_at", "displayed_at"]
