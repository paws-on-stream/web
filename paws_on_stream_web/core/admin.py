from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse

from .models import (
    DisplayDevice,
    DisplayLog,
    DisplayThemeAsset,
    DisplayThemeVersion,
    Settings,
    TelegramAccess,
)


@admin.register(Settings)
class SettingsAdmin(admin.ModelAdmin):
    """Admin for singleton application settings."""

    fieldsets = (
        (
            "Bot Configuration",
            {
                "fields": (
                    "bot_status",
                    "rate_limit_per_minute",
                    "max_message_length",
                    "auto_approve",
                    "spam_threshold",
                    "require_event_active",
                )
            },
        ),
        (
            "Display Settings",
            {
                "fields": (
                    "display_mode",
                    "overlay_theme",
                    "overlay_font_size",
                    "display_duration_sec",
                    "scroll_speed_px",
                )
            },
        ),
        ("Registration API", {"fields": ("reg_api_url", "reg_api_key")}),
        (
            "Event API",
            {"fields": ("event_api_url", "event_api_jsonq_filter")},
        ),
        ("System", {"fields": ("status_check_interval", "updated_at")}),
    )

    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj, _ = Settings.get_settings(), False
        return redirect(f"{reverse('admin:core_settings_change', args=(obj.id,))}")


@admin.register(DisplayDevice)
class DisplayDeviceAdmin(admin.ModelAdmin):
    list_display = ("device_id", "hostname", "location", "is_active", "last_seen")
    list_filter = ("is_active",)
    search_fields = ("device_id", "hostname", "location")
    list_editable = ("is_active",)


@admin.register(DisplayLog)
class DisplayLogAdmin(admin.ModelAdmin):
    list_display = (
        "message_preview",
        "device",
        "displayed_at",
        "display_duration_actual",
    )
    list_filter = ("displayed_at",)
    search_fields = ("message__participant__display_name",)
    readonly_fields = ("message", "device", "displayed_at", "display_duration_actual")

    def message_preview(self, obj):
        return f"{obj.message.participant.display_name}: {obj.message.content[:50]}"

    message_preview.short_description = "Message"


class DisplayThemeAssetInline(admin.TabularInline):
    model = DisplayThemeAsset
    extra = 0
    readonly_fields = ("asset_id", "file", "content_type", "sha256", "size")
    can_delete = False


@admin.register(DisplayThemeVersion)
class DisplayThemeVersionAdmin(admin.ModelAdmin):
    list_display = (
        "slug",
        "name",
        "version",
        "is_current",
        "uploaded_by",
        "created_at",
    )
    list_filter = ("is_current", "created_at")
    readonly_fields = (
        "slug",
        "name",
        "version",
        "manifest",
        "is_current",
        "uploaded_by",
        "created_at",
    )
    inlines = (DisplayThemeAssetInline,)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TelegramAccess)
class TelegramAccessAdmin(admin.ModelAdmin):
    list_display = (
        "telegram_id",
        "label",
        "is_active",
        "is_admin",
        "user",
        "last_login_at",
    )
    list_filter = ("is_active", "is_admin")
    search_fields = ("telegram_id", "label", "user__username")
    readonly_fields = ("user", "last_login_at", "created_at", "updated_at")
