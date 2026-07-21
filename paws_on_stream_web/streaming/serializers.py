from participants.models import Participant
from rest_framework import serializers

from streaming.models import Event, MediaAsset, Message


class EventSerializer(serializers.ModelSerializer):
    """Serializer for Event model."""

    is_active = serializers.BooleanField(required=False)

    class Meta:
        model = Event
        validators = []
        fields = [
            "id",
            "external_id",
            "name",
            "starts_at",
            "ends_at",
            "is_active",
            "allow_messages",
            "display_mode",
            "scroll_speed_px",
        ]
        read_only_fields = ["id", "external_id"]

    def validate(self, attrs):
        starts_at = attrs.get("starts_at", getattr(self.instance, "starts_at", None))
        ends_at = attrs.get("ends_at", getattr(self.instance, "ends_at", None))
        if starts_at and ends_at and ends_at <= starts_at:
            raise serializers.ValidationError(
                {"ends_at": "End time must be after start time."}
            )
        return attrs


class ParticipantSummarySerializer(serializers.Serializer):
    """Compact participant reference for Message."""

    display_name = serializers.CharField()
    telegram_id = serializers.IntegerField()
    checked_in = serializers.BooleanField(source="effective_checked_in")


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for Message model."""

    participant = ParticipantSummarySerializer(read_only=True)
    participant_id = serializers.IntegerField(write_only=True)
    media_asset_id = serializers.PrimaryKeyRelatedField(
        source="media_asset",
        queryset=MediaAsset.objects.all(),
        required=False,
        allow_null=True,
    )
    media_url = serializers.SerializerMethodField()
    media_format = serializers.CharField(source="media_asset.format", read_only=True)
    media_animated = serializers.BooleanField(
        source="media_asset.animated", read_only=True
    )
    media_width = serializers.IntegerField(source="media_asset.width", read_only=True)
    media_height = serializers.IntegerField(source="media_asset.height", read_only=True)
    media_duration_ms = serializers.IntegerField(
        source="media_asset.duration_ms", read_only=True
    )
    media_frame_count = serializers.IntegerField(
        source="media_asset.frame_count", read_only=True
    )
    media_has_alpha = serializers.BooleanField(
        source="media_asset.has_alpha", read_only=True
    )
    media_sha256 = serializers.CharField(source="media_asset.sha256", read_only=True)
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
            "media_asset_id",
            "media_format",
            "media_animated",
            "media_width",
            "media_height",
            "media_duration_ms",
            "media_frame_count",
            "media_has_alpha",
            "media_sha256",
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
        read_only_fields = [
            "id",
            "created_at",
            "approved_at",
            "displayed_at",
            "status",
            "spam_score",
            "rejection_reason",
            "approved_by",
        ]
        extra_kwargs = {"content": {"allow_blank": True}}

    def get_media_url(self, obj):
        if not obj.media_asset_id:
            return ""
        url = obj.media_asset.file.url
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request else url

    def create(self, validated_data):
        participant_id = validated_data.pop("participant_id", None)
        if participant_id is not None:
            participant = Participant.objects.filter(id=participant_id).first()
            if participant is None:
                raise serializers.ValidationError(
                    {"participant_id": ["Unknown participant."]}
                )
            validated_data["participant"] = participant
        return super().create(validated_data)
