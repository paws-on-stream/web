from django import forms

from core.form_utils import ReadableFormMixin
from core.models import DisplayDevice, Settings, TelegramAccess
from core.themes import available_theme_choices


class TelegramAccessForm(ReadableFormMixin, forms.ModelForm):
    ROLE_STAFF = "staff"
    ROLE_ADMIN = "admin"
    ROLE_CHOICES = ((ROLE_STAFF, "Staff"), (ROLE_ADMIN, "Admin"))

    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        label="Rolle",
        help_text="Admins dürfen zusätzlich Zugänge und Themes verwalten.",
    )

    class Meta:
        model = TelegramAccess
        fields = ["label", "is_active"]
        labels = {"label": "Name", "is_active": "Zugang freigeben"}
        help_texts = {
            "label": "Anzeigename für die interne Verwaltung.",
            "is_active": "Nur freigegebene Konten können sich am Dashboard anmelden.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].initial = (
            self.ROLE_ADMIN if self.instance.is_admin else self.ROLE_STAFF
        )

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.is_admin = self.cleaned_data["role"] == self.ROLE_ADMIN
        if commit:
            instance.save()
        return instance


class SettingsForm(ReadableFormMixin, forms.ModelForm):
    overlay_theme = forms.ChoiceField()

    class Meta:
        model = Settings
        fields = [
            "rate_limit_per_minute",
            "max_message_length",
            "bot_status",
            "overlay_theme",
            "overlay_font_size",
            "auto_approve",
            "spam_threshold",
            "display_duration_sec",
            "display_mode",
            "scroll_speed_px",
            "reg_api_url",
            "reg_api_key",
            "event_api_url",
            "event_api_jsonq_filter",
            "status_check_interval",
            "require_event_active",
        ]
        widgets = {
            "reg_api_key": forms.PasswordInput(
                render_value=True, attrs={"autocomplete": "off"}
            ),
            "event_api_jsonq_filter": forms.Textarea(
                attrs={"rows": 4, "spellcheck": "false"}
            ),
        }
        labels = {
            "rate_limit_per_minute": "Nachrichtenlimit pro Minute",
            "max_message_length": "Maximale Nachrichtenlänge",
            "bot_status": "Bot-Status",
            "overlay_theme": "Display-Theme",
            "overlay_font_size": "Schriftgröße",
            "auto_approve": "Nachrichten automatisch freigeben",
            "spam_threshold": "Spam-Grenzwert",
            "display_duration_sec": "Anzeigedauer in Sekunden",
            "display_mode": "Anzeigemodus",
            "scroll_speed_px": "Crawling-Geschwindigkeit",
            "reg_api_url": "URL des Registrierungssystems",
            "reg_api_key": "API-Schlüssel des Registrierungssystems",
            "event_api_url": "URL der Event-API",
            "event_api_jsonq_filter": "JSONQ-/jq-Filter",
            "status_check_interval": "Prüfintervall in Sekunden",
            "require_event_active": "Aktives Event voraussetzen",
        }
        help_texts = {
            "rate_limit_per_minute": "Maximale Nachrichten pro Teilnehmer und Minute.",
            "max_message_length": "Maximale Länge nach der serverseitigen Bereinigung.",
            "spam_threshold": (
                "Nur Nachrichten mit einem Spam-Score bis zu diesem Wert werden "
                "automatisch freigegeben."
            ),
            "overlay_theme": (
                "Zentrales Theme für Pygame und Browser-Vorschau; EAST 13 verwendet "
                "die Referenzgrafiken und das Pygame-Template."
            ),
            "display_duration_sec": "Mindestanzeigedauer einer Nachricht.",
            "scroll_speed_px": "Pixel pro Frame im Crawling-Modus.",
            "reg_api_url": (
                "Reg-System-Endpunkt ohne tg_user_id und key, zum Beispiel "
                "https://east.sachsenfurs.de/?page=TelegramInfo"
            ),
            "reg_api_key": (
                "Wird als geschützter Query-Parameter key an das Reg-System gesendet."
            ),
            "status_check_interval": "Intervall für Statusprüfungen in Sekunden.",
            "event_api_url": "Vollständige URL der externen Event-API.",
            "event_api_jsonq_filter": (
                "jq-Ausdruck für die JSON-Antwort, zum Beispiel "
                '[.[] | select(.attributes | type == "object" and has("live"))]'
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["overlay_theme"].choices = available_theme_choices()

    def clean_event_api_jsonq_filter(self):
        value = self.cleaned_data["event_api_jsonq_filter"].strip()
        if "\x00" in value:
            raise forms.ValidationError(
                "Der Filter enthält ein ungültiges Nullzeichen."
            )
        return value


class ThemeUploadForm(ReadableFormMixin, forms.Form):
    package = forms.FileField(
        label="Theme-Paket",
        help_text="ZIP mit theme.json (Schema v3) und allen deklarierten PNG-Assets.",
        widget=forms.ClearableFileInput(attrs={"accept": ".zip,application/zip"}),
    )


class DisplayDeviceForm(ReadableFormMixin, forms.ModelForm):
    class Meta:
        model = DisplayDevice
        fields = ["device_id", "hostname", "location", "is_active"]
        labels = {
            "device_id": "Geräte-ID",
            "hostname": "Hostname",
            "location": "Standort",
            "is_active": "Display aktiv",
        }
        help_texts = {
            "device_id": "Eindeutige Kennung des Raspberry Pi, zum Beispiel pi-01.",
            "location": "Optionale Beschreibung des Aufstellorts.",
            "is_active": "Inaktive Displays erhalten keine neuen Nachrichten.",
        }
