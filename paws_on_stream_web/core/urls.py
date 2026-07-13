from django.urls import path

from core.views import (
    DisplayDeviceDetailView,
    DisplayDeviceListView,
    SettingsView,
)

app_name = "core"

urlpatterns = [
    path("settings/", SettingsView.as_view(), name="settings"),
    path(
        "devices/", DisplayDeviceListView.as_view(), name="device_list"
    ),
    path(
        "devices/<int:pk>/",
        DisplayDeviceDetailView.as_view(),
        name="device_detail",
    ),
]
