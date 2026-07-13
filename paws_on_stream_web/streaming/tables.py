"""django-tables2 definitions for the streaming app."""

import django_tables2 as tables


class MessageTable(tables.Table):
    """Table definition for the Message model."""

    select = tables.CheckBoxColumn(accessor="pk", order_by=("-created_at",))

    class Meta:
        model = "streaming.Message"  # lazy reference to avoid import cycles
        fields = (
            "select",
            "participant",
            "content",
            "status",
            "created_at",
        )
        attrs = {"class": "table table-hover table-sm align-middle"}
