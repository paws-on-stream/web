"""Central runtime state shared by message acceptance and status consumers."""

from dataclasses import dataclass

from django.utils import timezone
from streaming.models import Event

from core.models import Settings


@dataclass(frozen=True)
class RuntimeStatus:
    """The central status relevant to bot and message processing."""

    app_settings: Settings
    active_event: Event | None
    display_mode: str
    display_mode_source: str
    messages_accepted: bool
    messages_reason: str | None


def get_runtime_status(app_settings: Settings | None = None) -> RuntimeStatus:
    """Return the authoritative global bot, event and message-acceptance state."""
    app_settings = app_settings or Settings.get_settings()
    now = timezone.now()
    active_event = (
        Event.objects.filter(
            is_active=True,
            starts_at__lte=now,
            ends_at__gte=now,
        )
        .order_by("starts_at")
        .first()
    )
    event_display_mode = active_event.display_mode if active_event else ""

    messages_reason = None
    if app_settings.bot_status == "maintenance":
        messages_reason = "maintenance"
    elif app_settings.bot_status != "online":
        messages_reason = "offline"
    elif active_event is not None and not active_event.allow_messages:
        messages_reason = "messages_disabled"
    elif app_settings.require_event_active and active_event is None:
        messages_reason = "no_event"

    return RuntimeStatus(
        app_settings=app_settings,
        active_event=active_event,
        display_mode=event_display_mode or app_settings.display_mode,
        display_mode_source="event" if event_display_mode else "global",
        messages_accepted=messages_reason is None,
        messages_reason=messages_reason,
    )
