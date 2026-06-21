from rest_framework import serializers

from participants.models import Participant


class ParticipantSerializer(serializers.ModelSerializer):
    """Serializer for Participant model."""

    class Meta:
        model = Participant
        fields = [
            "id",
            "telegram_id",
            "reg_id",
            "display_name",
            "checked_in",
            "last_status_check",
            "banned",
            "muted_until",
            "spam_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ParticipantCreateSerializer(serializers.ModelSerializer):
    """Simplified serializer for creating participants."""

    class Meta:
        model = Participant
        fields = ["telegram_id", "display_name"]

    def validate_display_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Display name cannot be blank.")
        return value.strip()
