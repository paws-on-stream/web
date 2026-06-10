import factory

from participants.models import Participant


class ParticipantFactory(factory.django.DjangoModelFactory):
    """Erzeugt ein Participant-Objekt mit sinnvollen Default-Werten."""

    class Meta:
        model = Participant
        django_get_or_create = ("telegram_id",)

    display_name = factory.Faker("name")
    telegram_id = factory.Faker("random_number", digits=19)
