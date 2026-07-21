from core.form_utils import ReadableFormMixin
from django import forms

from streaming.models import Event


class EventForm(ReadableFormMixin, forms.ModelForm):
    display_mode = forms.ChoiceField(
        required=False,
        label="Anzeigemodus",
        choices=(
            ("", "Globale Einstellung verwenden"),
            ("chat", "Chat"),
            ("crawling", "Crawling"),
        ),
    )

    class Meta:
        model = Event
        fields = [
            "name",
            "starts_at",
            "ends_at",
            "is_active",
            "allow_messages",
            "display_mode",
            "scroll_speed_px",
        ]
        labels = {
            "name": "Name",
            "starts_at": "Beginn",
            "ends_at": "Ende",
            "is_active": "Event aktiv",
            "allow_messages": "Nachrichten erlauben",
            "scroll_speed_px": "Crawling-Geschwindigkeit",
        }
        help_texts = {
            "is_active": "Es kann immer nur ein Event gleichzeitig aktiv sein.",
            "allow_messages": (
                "Deaktivieren, um neue Nachrichten für dieses Event zu blockieren."
            ),
            "display_mode": (
                "Leer übernimmt den globalen Anzeigemodus aus den Settings."
            ),
            "scroll_speed_px": (
                "Leer übernimmt die globale Geschwindigkeit; Wert in Pixeln pro Frame."
            ),
        }
        widgets = {
            "starts_at": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}
            ),
            "ends_at": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}
            ),
        }

    def clean(self):
        cleaned = super().clean()
        starts_at = cleaned.get("starts_at")
        ends_at = cleaned.get("ends_at")
        if starts_at and ends_at and ends_at <= starts_at:
            self.add_error("ends_at", "Das Ende muss nach dem Beginn liegen.")
        return cleaned
