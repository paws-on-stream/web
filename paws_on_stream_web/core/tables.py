"""django-tables2 definitions for the core app."""

import django_tables2 as tables
from django.utils.html import format_html

from core.models import DisplayDevice, DisplayLog


class DisplayDeviceTable(tables.Table):
    """Table definition for the DisplayDevice model."""

    select = tables.CheckBoxColumn(accessor="pk")
    device_id = tables.Column(linkify=True, order_by="device_id")
    hostname = tables.Column(linkify=True, order_by="hostname")
    is_active = tables.Column(order_by="is_active", verbose_name="Active")
    last_seen = tables.Column(order_by="last_seen", verbose_name="Last seen")

    class Meta:
        model = DisplayDevice
        fields = (
            "select",
            "device_id",
            "hostname",
            "location",
            "is_active",
            "last_seen",
        )
        attrs = {"class": "table table-hover table-sm align-middle"}

    def render_select(self, record):
        return format_html(
            '<input type="checkbox" name="select" value="{}" class="form-check-input">',
            record.pk,
        )

    def render_device_id(self, value):
        return format_html("<code>{}</code>", value)

    def render_is_active(self, value):
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            "success" if value else "secondary",
            "Active" if value else "Inactive",
        )

    def render_last_seen(self, value):
        if not value:
            return "—"
        return value.strftime("%d.%m.%Y %H:%M")


class DisplayLogTable(tables.Table):
    participant = tables.Column(
        empty_values=(),
        order_by="message__participant__display_name",
    )
    message = tables.Column(empty_values=(), order_by="message__created_at")
    device = tables.Column(order_by="device__device_id", linkify=True)
    displayed_at = tables.Column(order_by="displayed_at", verbose_name="Displayed")
    display_duration_actual = tables.Column(verbose_name="Duration (s)")

    class Meta:
        model = DisplayLog
        fields = (
            "participant",
            "message",
            "device",
            "displayed_at",
            "display_duration_actual",
        )
        attrs = {"class": "table table-hover table-sm align-middle"}

    def render_participant(self, record):
        return record.message.participant.display_name

    def render_message(self, record):
        message = record.message
        if message.content:
            return message.content[:80]
        return f"[{message.get_media_type_display()}]"

    def render_displayed_at(self, value):
        return value.strftime("%d.%m.%Y %H:%M:%S")

    def render_display_duration_actual(self, value):
        return value if value is not None else "—"
