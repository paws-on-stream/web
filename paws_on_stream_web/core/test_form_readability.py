from django.test import RequestFactory, TestCase
from participants.forms import ParticipantForm
from streaming.forms import EventForm

from core.form_utils import ReadableAuthenticationForm
from core.forms import DisplayDeviceForm, SettingsForm


class ReadableFormsTest(TestCase):
    def test_settings_widgets_use_matching_bootstrap_classes_and_help_ids(self):
        form = SettingsForm()

        assert "form-select" in form.fields["display_mode"].widget.attrs["class"]
        assert "form-control" in form.fields["event_api_url"].widget.attrs["class"]
        assert "form-check-input" in form.fields["auto_approve"].widget.attrs["class"]
        assert form.fields["event_api_url"].widget.attrs["aria-describedby"] == (
            "id_event_api_url_help"
        )

    def test_invalid_field_gets_visible_and_accessible_error_state(self):
        form = DisplayDeviceForm(data={"device_id": "", "hostname": "", "location": ""})

        assert not form.is_valid()
        widget = form.fields["device_id"].widget
        assert "is-invalid" in widget.attrs["class"]
        assert widget.attrs["aria-invalid"] == "true"
        assert "id_device_id_error" in widget.attrs["aria-describedby"]

    def test_participant_form_uses_select_switch_and_datetime_local(self):
        form = ParticipantForm()

        assert "form-select" in form.fields["checked_in_override"].widget.attrs["class"]
        assert "form-check-input" in form.fields["banned"].widget.attrs["class"]
        assert form.fields["muted_until"].widget.input_type == "datetime-local"

    def test_event_form_has_german_choices_dates_and_validation(self):
        form = EventForm(
            data={
                "name": "Test",
                "starts_at": "2026-08-02T14:00",
                "ends_at": "2026-08-02T13:00",
                "display_mode": "",
                "scroll_speed_px": "",
            }
        )

        assert form.fields["starts_at"].widget.input_type == "datetime-local"
        assert ("", "Globale Einstellung verwenden") in form.fields[
            "display_mode"
        ].choices
        assert not form.is_valid()
        assert "Das Ende muss nach dem Beginn liegen." in form.errors["ends_at"]

    def test_login_form_uses_readable_widgets(self):
        request = RequestFactory().post("/auth/login/")
        form = ReadableAuthenticationForm(request=request)

        assert "form-control" in form.fields["username"].widget.attrs["class"]
        assert form.fields["username"].widget.attrs["autocomplete"] == "username"
        assert form.fields["password"].widget.attrs["autocomplete"] == (
            "current-password"
        )
