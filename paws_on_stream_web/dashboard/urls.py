from django.urls import path

from dashboard.views import dashboard, dashboard_live, dashboard_test_message

app_name = "dashboard"

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("live/", dashboard_live, name="dashboard_live"),
    path("test-message/", dashboard_test_message, name="dashboard_test_message"),
]
