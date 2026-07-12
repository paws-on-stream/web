from django.urls import path

from streaming.views import (
    EventDetailView,
    EventListView,
    MessageDetailView,
    MessageListView,
)

app_name = "streaming"

urlpatterns = [
    path("messages/", MessageListView.as_view(), name="message_list"),
    path("messages/<uuid:pk>/", MessageDetailView.as_view(), name="message_detail"),
    path("events/", EventListView.as_view(), name="event_list"),
    path("events/<int:pk>/", EventDetailView.as_view(), name="event_detail"),
]
