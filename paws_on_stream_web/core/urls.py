from django.urls import path

from core.views import SettingsView

app_name = "core"

urlpatterns = [
    path("settings/", SettingsView.as_view(), name="settings"),
]
