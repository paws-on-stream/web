from django import forms
from django.contrib.auth.forms import AuthenticationForm


class ReadableFormMixin:
    """Apply consistent Bootstrap and accessibility attributes to Django forms."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            widget = field.widget
            bound = self[name]
            classes = set(widget.attrs.get("class", "").split())
            if isinstance(widget, forms.CheckboxInput):
                classes.add("form-check-input")
            elif isinstance(widget, forms.Select):
                classes.add("form-select")
            else:
                classes.add("form-control")
            widget.attrs["class"] = " ".join(sorted(classes))

            if field.help_text:
                widget.attrs["aria-describedby"] = f"{bound.id_for_label}_help"

    def full_clean(self):
        super().full_clean()
        for name in self.errors:
            if name not in self.fields:
                continue
            field = self.fields[name]
            widget = field.widget
            classes = set(widget.attrs.get("class", "").split())
            classes.add("is-invalid")
            widget.attrs["class"] = " ".join(sorted(classes))
            widget.attrs["aria-invalid"] = "true"
            described_by = widget.attrs.get("aria-describedby", "").split()
            error_id = f"{self[name].id_for_label}_error"
            if error_id not in described_by:
                described_by.append(error_id)
            widget.attrs["aria-describedby"] = " ".join(described_by)


class ReadableAuthenticationForm(ReadableFormMixin, AuthenticationForm):
    username = forms.CharField(
        label="Benutzername",
        widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "username"}),
    )
    password = forms.CharField(
        label="Passwort",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
