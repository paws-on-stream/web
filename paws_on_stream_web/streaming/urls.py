from django.urls import path

from streaming.views import MessageDetailView, MessageListView

app_name = "streaming"

urlpatterns = [
    path("messages/", MessageListView.as_view(), name="message_list"),
    path("messages/<uuid:pk>/", MessageDetailView.as_view(), name="message_detail"),
]
