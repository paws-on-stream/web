from django.urls import path

from streaming.views import (
    EventCreateView,
    EventDeleteView,
    EventDetailView,
    EventListView,
    EventUpdateView,
    MessageDetailView,
    MessageListView,
)

app_name = "streaming"

urlpatterns = [
    path("messages/", MessageListView.as_view(), name="message_list"),
    path("messages/<uuid:pk>/", MessageDetailView.as_view(), name="message_detail"),
    path("events/", EventListView.as_view(), name="event_list"),
    path("events/new/", EventCreateView.as_view(), name="event_create"),
    path("events/<int:pk>/", EventDetailView.as_view(), name="event_detail"),
    path("events/<int:pk>/edit/", EventUpdateView.as_view(), name="event_edit"),
    path("events/<int:pk>/delete/", EventDeleteView.as_view(), name="event_delete"),
]
