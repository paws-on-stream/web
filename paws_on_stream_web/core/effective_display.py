from dataclasses import dataclass

from django.utils import timezone
from streaming.models import Event

from core.models import Settings


@dataclass(frozen=True)
class EffectiveDisplaySettings:
    display_mode: str
    scroll_speed_px: int
    event: Event | None
    display_mode_source: str
    scroll_speed_source: str


def get_effective_display_settings(
    app_settings: Settings | None = None,
) -> EffectiveDisplaySettings:
    app_settings = app_settings or Settings.get_settings()
    now = timezone.now()
    active_event = Event.objects.filter(
        is_active=True,
        starts_at__lte=now,
        ends_at__gte=now,
    ).first()

    event_display_mode = active_event.display_mode if active_event else ""
    event_scroll_speed = active_event.scroll_speed_px if active_event else None

    return EffectiveDisplaySettings(
        display_mode=event_display_mode or app_settings.display_mode,
        scroll_speed_px=(
            event_scroll_speed
            if event_scroll_speed is not None
            else app_settings.scroll_speed_px
        ),
        event=active_event,
        display_mode_source="event" if event_display_mode else "global",
        scroll_speed_source="event" if event_scroll_speed is not None else "global",
    )
