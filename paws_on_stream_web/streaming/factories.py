from datetime import UTC, datetime

import factory
from participants.factories import ParticipantFactory

from streaming.models import Event, Message


class EventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Event
        django_get_or_create = ("name",)

    name = factory.Faker("domain_word")
    starts_at = factory.Faker(
        "date_time_between",
        tzinfo=UTC,
        start_date="-12h",
        end_date=datetime.now(tz=UTC),
    )
    ends_at = factory.Faker(
        "date_time_between",
        tzinfo=UTC,
        start_date=datetime.now(tz=UTC),
        end_date="+12h",
    )


class MessageFactory(factory.django.DjangoModelFactory):
    """Erzeugt ein Message-Objekt mit sinnvollen Werten."""

    class Meta:
        model = Message
        django_get_or_create = ("id",)

    id = factory.Faker("uuid4")
    participant = factory.SubFactory(ParticipantFactory)


class TextMessageFactory(MessageFactory):
    content = factory.Faker("sentence")
    media_type = "text"
