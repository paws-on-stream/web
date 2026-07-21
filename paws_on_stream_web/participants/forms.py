from core.form_utils import ReadableFormMixin
from django import forms

from participants.models import Participant


class ParticipantForm(ReadableFormMixin, forms.ModelForm):
    class Meta:
        model = Participant
        fields = [
            "telegram_id",
            "reg_id",
            "display_name",
            "checked_in_override",
            "banned",
            "muted_until",
        ]
        labels = {
            "telegram_id": "Telegram-ID",
            "reg_id": "Registrierungs-ID",
            "display_name": "Anzeigename",
            "checked_in_override": "Check-in dauerhaft überschreiben",
            "banned": "Teilnehmer sperren",
            "muted_until": "Stummgeschaltet bis",
        }
        help_texts = {
            "telegram_id": "Numerische Telegram-ID des Teilnehmers.",
            "reg_id": "Optionale ID aus dem Registrierungssystem.",
            "checked_in_override": (
                "Automatisch übernimmt den Status des Registrierungssystems."
            ),
            "banned": "Gesperrte Teilnehmer können keine Nachrichten einsenden.",
            "muted_until": (
                "Leer lassen, wenn keine zeitliche Stummschaltung aktiv ist."
            ),
        }
        widgets = {
            "muted_until": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}
            )
        }
