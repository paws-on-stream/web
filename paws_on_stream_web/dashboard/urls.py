from django.urls import path

from dashboard.views import EventsView, ParticipantsView, SettingsView

app_name = "dashboard"

urlpatterns = [
    path("dashboard/participants/", ParticipantsView.as_view(), name="participants"),
    path("dashboard/events/", EventsView.as_view(), name="events"),
    path("dashboard/settings/", SettingsView.as_view(), name="settings"),
]
