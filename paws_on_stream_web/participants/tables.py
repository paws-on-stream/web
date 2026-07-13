"""django-tables2 definitions for the participants app."""

import django_tables2 as tables

from participants.models import Participant


class ParticipantTable(tables.Table):
    """Table definition for the Participant model."""

    select = tables.CheckBoxColumn(accessor="pk")

    class Meta:
        model = Participant
        fields = (
            "select",
            "display_name",
            "telegram_id",
            "checked_in",
            "banned",
            "muted_until",
            "spam_count",
            "created_at",
        )
        attrs = {"class": "table table-hover table-sm align-middle"}
