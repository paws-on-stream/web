from django import forms

from participants.models import Participant


class ParticipantForm(forms.ModelForm):
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name not in {"banned"}:
                field.widget.attrs.update({"class": "form-control"})
        self.fields["checked_in_override"].widget.attrs["class"] = "form-select"
