from django.urls import path

from dashboard.views import dashboard, dashboard_live, system_status

app_name = "dashboard"

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("live/", dashboard_live, name="dashboard_live"),
    path("status/", system_status, name="system_status"),
]
