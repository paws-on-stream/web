import factory
from streaming.factories import MessageFactory

from core.models import DisplayDevice, DisplayLog, Settings


class SettingsFactory(factory.django.DjangoModelFactory):
    """Erzeugt ein Settings‑Objekt mit allen Default‑Werten."""

    class Meta:
        model = Settings
        # Wir wollen explizit **nicht** das PK‑Handling von get_settings überschreiben.
        django_get_or_create = ("id",)

    rate_limit_per_minute = 10
    max_message_length = 4096
    bot_status = "online"
    overlay_theme = "default"
    overlay_font_size = 24
    auto_approve = False
    display_duration_sec = 8
    reg_api_url = ""
    reg_api_key = ""
    status_check_interval = 300
    require_event_active = True
    display_mode = "chat"
    scroll_speed_px = 3


class DisplayDeviceFactory(factory.django.DjangoModelFactory):
    """Factory für DisplayDevice – erzeugt gültige Objekte mit sinnvollen Defaults."""

    class Meta:
        model = DisplayDevice
        django_get_or_create = ("device_id",)

    device_id = factory.Sequence(lambda n: f"dev-{n:04d}")
    hostname = factory.Faker("hostname")


class DisplayLogFactory(factory.django.DjangoModelFactory):
    """Erzeugt ein Display Log-Objekt mit sinnvollen Werten."""

    class Meta:
        model = DisplayLog

    device = factory.SubFactory(DisplayDeviceFactory)
    message = factory.SubFactory(MessageFactory)
