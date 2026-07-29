from django.urls import path

from dashboard.views import dashboard, dashboard_live

app_name = "dashboard"

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("live/", dashboard_live, name="dashboard_live"),
]
