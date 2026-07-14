from django.urls import path

from participants.views import (
    ParticipantDetailView,
    ParticipantListView,
    ParticipantUpdateView,
    ParticipantDeleteView,
)

app_name = "participants"

urlpatterns = [
    path("participants/", ParticipantListView.as_view(), name="participant_list"),
    path(
        "participants/<int:pk>/",
        ParticipantDetailView.as_view(),
        name="participant_detail",
    ),
    path(
        "participants/<int:pk>/edit/",
        ParticipantUpdateView.as_view(),
        name="participant_edit",
    ),
    path(
        "participants/<int:pk>/delete/",
        ParticipantDeleteView.as_view(),
        name="participant_delete",
    ),
]
