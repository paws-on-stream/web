"""django-tables2 definitions for the streaming app."""

import django_tables2 as tables
from django.utils.html import format_html

from streaming.models import Event, Message


class MessageTable(tables.Table):
    """Table definition for the Message model."""

    select = tables.CheckBoxColumn(accessor="pk")
    participant = tables.Column(linkify=True, order_by="participant__display_name")
    event = tables.Column(order_by="event__starts_at", empty_values=())
    media_type = tables.Column(order_by="media_type")
    status = tables.Column(order_by="status")
    content = tables.Column(order_by="content")
    created_at = tables.Column(order_by="created_at", verbose_name="Created")

    class Meta:
        model = Message
        fields = (
            "select",
            "participant",
            "event",
            "media_type",
            "status",
            "content",
            "created_at",
        )
        attrs = {"class": "table table-hover table-sm align-middle"}

    def render_select(self, record):
        return format_html(
            '<input type="checkbox" name="select" value="{}" class="form-check-input">',
            record.pk,
        )

    def render_event(self, record):
        if not record.event:
            return "—"
        return record.event.name

    def render_media_type(self, value, record):
        media_type = record.media_type
        variant = {
            "text": "secondary",
            "photo": "primary",
            "gif": "info",
            "sticker": "warning",
        }.get(media_type, "secondary")
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            variant,
            value or media_type or "unknown",
        )

    def render_status(self, value, record):
        status = record.status
        variant = {
            "pending": "warning text-dark",
            "approved": "success",
            "rejected": "danger",
            "displayed": "secondary",
        }.get(status, "secondary")
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            variant,
            value or status,
        )

    def render_content(self, value, record):
        snippet = (value or record.raw_content or "")[:80]
        if record.media_type in {"photo", "gif", "sticker"}:
            label = f"{record.get_media_type_display()} media"
        else:
            label = snippet or "—"
        return format_html(
            (
                '<span class="text-truncate d-inline-block" '
                'style="max-width: 28rem;">{}</span>'
            ),
            label,
        )

    def render_created_at(self, value):
        return value.strftime("%d.%m.%Y %H:%M")


class EventTable(tables.Table):
    """Table definition for the Event model."""

    select = tables.CheckBoxColumn(accessor="pk")
    name = tables.Column(linkify=True, order_by="name")
    is_active = tables.Column(order_by="is_active", verbose_name="Active")
    allow_messages = tables.Column(order_by="allow_messages", verbose_name="Msgs")
    display_mode = tables.Column(order_by="display_mode")
    starts_at = tables.Column(order_by="starts_at", verbose_name="Start")
    ends_at = tables.Column(order_by="ends_at", verbose_name="End")

    class Meta:
        model = Event
        fields = (
            "select",
            "name",
            "is_active",
            "allow_messages",
            "display_mode",
            "starts_at",
            "ends_at",
        )
        attrs = {"class": "table table-hover table-sm align-middle"}

    def render_select(self, record):
        return format_html(
            '<input type="checkbox" name="select" value="{}" class="form-check-input">',
            record.pk,
        )

    def render_is_active(self, value):
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            "success" if value else "secondary",
            "Active" if value else "Inactive",
        )

    def render_allow_messages(self, value):
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            "success" if value else "danger",
            "Yes" if value else "No",
        )

    def render_display_mode(self, value):
        return value or "—"

    def render_starts_at(self, value):
        return value.strftime("%d.%m.%Y %H:%M")

    def render_ends_at(self, value):
        return value.strftime("%d.%m.%Y %H:%M")
