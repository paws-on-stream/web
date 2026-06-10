from django.contrib import admin

from .models import Participant


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "telegram_id",
        "checked_in",
        "banned",
        "spam_count",
        "created_at",
    )
    list_filter = ("checked_in", "banned", "created_at")
    search_fields = ("display_name", "telegram_id")
    list_editable = ("checked_in", "banned")
    readonly_fields = ("telegram_id", "spam_count", "created_at", "updated_at")
    fieldsets = (
        ("Identity", {"fields": ("telegram_id", "display_name", "reg_id")}),
        (
            "Status",
            {"fields": ("checked_in", "banned", "muted_until", "last_status_check")},
        ),
        ("Spam", {"fields": ("spam_count",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
