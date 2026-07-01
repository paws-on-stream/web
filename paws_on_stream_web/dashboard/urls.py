from dashboard.views import ParticipantsView, EventsView, SettingsView
from django.urls import path

app_name = "dashboard"

urlpatterns = [
    path("dashboard/participants/", ParticipantsView.as_view(), name="participants"),
    path("dashboard/events/", EventsView.as_view(), name="events"),
    path("dashboard/settings/", SettingsView.as_view(), name="settings"),
]
