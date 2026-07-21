from rest_framework import serializers

from participants.models import Participant


class ParticipantSerializer(serializers.ModelSerializer):
    """Serializer for Participant model."""

    checked_in = serializers.BooleanField(required=False)
    registration_checked_in = serializers.BooleanField(
        source="checked_in", read_only=True
    )

    class Meta:
        model = Participant
        fields = [
            "id",
            "telegram_id",
            "reg_id",
            "display_name",
            "checked_in",
            "registration_checked_in",
            "checked_in_override",
            "last_status_check",
            "banned",
            "muted_until",
            "spam_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["checked_in"] = instance.effective_checked_in
        return data


class ParticipantCreateSerializer(serializers.ModelSerializer):
    """Simplified serializer for creating participants."""

    class Meta:
        model = Participant
        fields = ["telegram_id", "display_name"]

    def validate_display_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Display name cannot be blank.")
        return value.strip()
