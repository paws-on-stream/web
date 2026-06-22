from datetime import UTC, datetime

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from streaming.models import Event, Message
from streaming.serializers import EventSerializer, MessageSerializer


class EventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer


class MessageViewSet(viewsets.ModelViewSet):
    queryset = Message.objects.select_related("participant", "event").all()
    serializer_class = MessageSerializer

    @action(detail=False, methods=["get"])
    def pending(self, request):  # noqa: ARG002
        queryset = self.queryset.filter(status="pending")
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="displayed")
    def displayed(self, request):  # noqa: ARG002
        queryset = self.queryset.filter(status="displayed")
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):  # noqa: ARG002
        message = self.get_object()
        message.status = "approved"
        message.approved_at = datetime.now(tz=UTC)
        message.approved_by = request.user if request.user.is_authenticated else None
        message.save(update_fields=["status", "approved_at", "approved_by"])
        return Response(self.get_serializer(message).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):  # noqa: ARG002
        message = self.get_object()
        reason = request.data.get("rejection_reason", "unknown")
        message.status = "rejected"
        message.rejection_reason = reason
        message.save(update_fields=["status", "rejection_reason"])
        return Response(self.get_serializer(message).data)

    @action(detail=True, methods=["post"])
    def display(self, request, pk=None):  # noqa: ARG002
        message = self.get_object()
        message.status = "displayed"
        message.displayed_at = datetime.now(tz=UTC)
        message.save(update_fields=["status", "displayed_at"])
        return Response(self.get_serializer(message).data)
