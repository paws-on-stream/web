from django.urls import path

from participants.views import ParticipantDetailView, ParticipantListView

app_name = "participants"

urlpatterns = [
    path("participants/", ParticipantListView.as_view(), name="participant_list"),
    path(
        "participants/<int:pk>/",
        ParticipantDetailView.as_view(),
        name="participant_detail",
    ),
]
