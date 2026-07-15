"""django-tables2 definitions for the core app."""

import django_tables2 as tables
from django.utils.html import format_html

from core.models import DisplayDevice


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
