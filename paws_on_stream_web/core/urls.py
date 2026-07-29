from django.urls import path

from core.views import (
    DisplayDeviceDeleteView,
    DisplayDeviceDetailView,
    DisplayDeviceListView,
    DisplayDeviceUpdateView,
    DisplayLogListView,
    DisplayThemeEditorView,
    DisplayThemeManagementView,
    SettingsUpdateView,
    SettingsView,
    TelegramAccessListView,
    TelegramAccessUpdateView,
    WebDisplayAccessView,
)

app_name = "core"

urlpatterns = [
    path("settings/", SettingsView.as_view(), name="settings"),
    path("settings/edit/", SettingsUpdateView.as_view(), name="settings_edit"),
    path("devices/", DisplayDeviceListView.as_view(), name="device_list"),
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
    path("logs/", DisplayLogListView.as_view(), name="log_list"),
    path(
        "telegram-access/",
        TelegramAccessListView.as_view(),
        name="telegram_access_list",
    ),
    path(
        "telegram-access/<int:pk>/edit/",
        TelegramAccessUpdateView.as_view(),
        name="telegram_access_edit",
    ),
    path("web-display/", WebDisplayAccessView.as_view(), name="web_display_access"),
    path("themes/", DisplayThemeManagementView.as_view(), name="theme_management"),
    path(
        "themes/<int:pk>/edit/",
        DisplayThemeEditorView.as_view(),
        name="theme_editor",
    ),
]
