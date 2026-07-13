"""django-tables2 definitions for the core app."""

import django_tables2 as tables

from core.models import DisplayDevice


class DisplayDeviceTable(tables.Table):
    """Table definition for the DisplayDevice model."""

    select = tables.CheckBoxColumn(accessor="pk")
    is_active = tables.BooleanColumn(order_by=("is_active",))

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
