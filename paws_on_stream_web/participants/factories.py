import factory

from participants.models import Participant

TELEGRAM_ID_MAX = 9_223_372_036_854_775_807


class ParticipantFactory(factory.django.DjangoModelFactory):
    """Erzeugt ein Participant-Objekt mit sinnvollen Default-Werten."""

    class Meta:
        model = Participant
        django_get_or_create = ("telegram_id",)

    display_name = factory.Faker("name")
    telegram_id = factory.Sequence(lambda n: TELEGRAM_ID_MAX - n)
