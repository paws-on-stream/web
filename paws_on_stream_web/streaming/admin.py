from django.contrib import admin

from .models import Event, Message


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("name", "starts_at", "ends_at", "is_active", "allow_messages")
    list_filter = ("is_active", "allow_messages")
    search_fields = ("name",)
    list_editable = ("is_active", "allow_messages")
    fieldsets = (
        ("Event Details", {"fields": ("name", "starts_at", "ends_at")}),
        ("Status", {"fields": ("is_active", "allow_messages")}),
        ("Display Override", {"fields": ("display_mode", "scroll_speed_px")}),
    )


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("participant_short", "content_short", "status", "media_type", "event", "created_at")
    list_filter = ("status", "media_type", "created_at")
    search_fields = ("content", "participant__display_name")
    readonly_fields = ("participant", "content", "raw_content", "media_type", "media_url", "sticker_emoji", "spam_score", "created_at")
    fieldsets = (
        ("Message", {"fields": ("participant", "content", "raw_content", "media_type", "media_url", "sticker_emoji")}),
        ("Status", {"fields": ("status", "rejection_reason", "approved_by", "approved_at", "displayed_at")}),
        ("Metadata", {"fields": ("event", "spam_score", "created_at")}),
    )

    def participant_short(self, obj):
        return str(obj.participant)
    participant_short.short_description = "Participant"

    def content_short(self, obj):
        return obj.content[:60] + "..." if len(obj.content) > 60 else obj.content
    content_short.short_description = "Content"
