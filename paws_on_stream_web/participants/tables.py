"""django-tables2 definitions for the participants app."""

import django_tables2 as tables
from django.utils.html import format_html

from participants.models import Participant


class ParticipantTable(tables.Table):
    """Table definition for the Participant model."""

    select = tables.CheckBoxColumn(accessor="pk")

    display_name = tables.Column(linkify=True, order_by="display_name")
    telegram_id = tables.Column(order_by="telegram_id")
    checked_in = tables.Column(order_by="checked_in", verbose_name="In")
    banned = tables.Column(order_by="banned")
    muted_until = tables.Column(order_by="muted_until", verbose_name="Muted")
    spam_count = tables.Column(order_by="spam_count")
    created_at = tables.Column(order_by="created_at", verbose_name="Joined")

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
        attrs = {
            "class": "table table-hover table-sm align-middle",
            "id": "participant-table",
        }

    def render_select(self, record):
        return format_html(
            '<input type="checkbox" name="select" value="{}" class="form-check-input">',
            record.pk,
        )

    def render_display_name(self, record):
        # Telegram-style avatar with initials
        initials = record.display_name[:2].upper() if record.display_name else "?"
        colors = ["#4CAF50", "#2196F3", "#FF9800", "#9C27B0", "#F44336", "#00BCD4"]
        color_idx = abs(hash(record.telegram_id)) % len(colors)
        bg_color = colors[color_idx]
        avatar = format_html(
            '<span class="d-inline-flex align-items-center gap-2">'
            '<span class="d-inline-flex align-items-center justify-content-center '
            'rounded-circle text-white fw-bold" style="width:28px;height:28px;'
            'background-color:{};font-size:0.75rem;">{}</span>'
            "<span>{}</span></span>",
            bg_color,
            initials,
            record.display_name or "Unknown",
        )
        return avatar

    def render_checked_in(self, record):
        if record.checked_in:
            return format_html('<span class="badge bg-success">{}</span>', "✓")
        return format_html('<span class="badge bg-secondary">{}</span>', "✗")

    def render_banned(self, record):
        if record.banned:
            return format_html('<span class="badge bg-danger">{}</span>', "Banned")
        return format_html('<span class="badge bg-success">{}</span>', "Active")

    def render_muted_until(self, record):
        if record.muted_until:
            return format_html(
                '<span class="badge bg-info">until {}</span>',
                record.muted_until.strftime("%H:%M"),
            )
        return "—"

    def render_spam_count(self, record):
        if record.spam_count > 0:
            return format_html(
                '<span class="badge bg-warning text-dark">{}</span>',
                record.spam_count,
            )
        return "0"

    def render_created_at(self, record):
        return record.created_at.strftime("%d.%m.%Y")
