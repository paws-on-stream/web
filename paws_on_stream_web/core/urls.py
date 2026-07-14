from django.urls import path

from core.views import (
    DisplayDeviceDetailView,
    DisplayDeviceListView,
    DisplayDeviceUpdateView,
    DisplayDeviceDeleteView,
    SettingsView,
    SettingsUpdateView,
)

app_name = "core"

urlpatterns = [
    path("settings/", SettingsView.as_view(), name="settings"),
    path("settings/edit/", SettingsUpdateView.as_view(), name="settings_edit"),
    path(
        "devices/", DisplayDeviceListView.as_view(), name="device_list"
    ),
    path(
        "devices/<int:pk>/",
        DisplayDeviceDetailView.as_view(),
        name="device_detail",
    ),
    path(
        "devices/<int:pk>/edit/",
        DisplayDeviceUpdateView.as_view(),
        name="device_edit",
    ),
    path(
        "devices/<int:pk>/delete/",
        DisplayDeviceDeleteView.as_view(),
        name="device_delete",
    ),
]
