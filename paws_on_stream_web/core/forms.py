from django import forms

from core.models import Settings


class SettingsForm(forms.ModelForm):
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
            "reg_api_key": forms.PasswordInput(render_value=True),
            "event_api_jsonq_filter": forms.Textarea(
                attrs={"rows": 4, "spellcheck": "false"}
            ),
        }
        help_texts = {
            "rate_limit_per_minute": "Maximale Nachrichten pro Teilnehmer und Minute.",
            "max_message_length": "Maximale Länge nach der serverseitigen Bereinigung.",
            "spam_threshold": (
                "Nur Nachrichten mit einem Spam-Score bis zu diesem Wert werden "
                "automatisch freigegeben."
            ),
            "overlay_theme": "Name des Themes, das der Display-Client laden soll.",
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
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            else:
                field.widget.attrs["class"] = "form-control"
        for name in ("bot_status", "display_mode"):
            self.fields[name].widget.attrs["class"] = "form-select"

    def clean_event_api_jsonq_filter(self):
        value = self.cleaned_data["event_api_jsonq_filter"].strip()
        if "\x00" in value:
            raise forms.ValidationError(
                "Der Filter enthält ein ungültiges Nullzeichen."
            )
        return value
