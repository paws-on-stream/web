from datetime import UTC, datetime, timedelta

from core.models import DisplayDevice, DisplayLog, Settings
from django.http import HttpResponseBadRequest
from django.urls import reverse
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, UpdateView
from django_tables2 import SingleTableView
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from streaming.models import Event, Message
from streaming.sanitization import sanitize_content
from streaming.serializers import EventSerializer, MessageSerializer
from streaming.tables import EventTable, MessageTable


class EventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer


class MessageViewSet(viewsets.ModelViewSet):
    queryset = Message.objects.select_related("participant", "event").all()
    serializer_class = MessageSerializer

    # --- create: sanitization + auto-approve ---------------------------------

    def create(self, request, *args, **kwargs):
        settings = Settings.get_settings()
        raw_content = request.data.get("content", "").strip()
        content = sanitize_content(raw_content, max_length=settings.max_message_length)

        # Validate length after sanitization
        if not content:
            return Response(
                {"content": ["Message is empty after sanitization."]},
                status=400,
            )

        # Build modified data dict (don't mutate request.data)
        data = request.data.copy()
        data["content"] = content
        data["raw_content"] = raw_content

        # Auto-approve if enabled
        if settings.auto_approve:
            data["status"] = "approved"

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=201)

    # --- approve: pending → approved ------------------------------------------

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):  # noqa: ARG002
        message = self.get_object()
        if message.status != "pending":
            return Response(
                {
                    "status": [
                        f"Message is already '{message.status}'"
                        "— only pending messages can be approved."
                    ]
                },
                status=400,
            )
        message.status = "approved"
        message.approved_at = datetime.now(tz=UTC)
        message.approved_by = request.user if request.user.is_authenticated else None
        message.save(update_fields=["status", "approved_at", "approved_by"])
        return Response(self.get_serializer(message).data)

    # --- reject: pending → rejected (validate reason) -------------------------

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):  # noqa: ARG002
        message = self.get_object()
        if message.status != "pending":
            return Response(
                {
                    "status": [
                        f"Message is already '{message.status}'"
                        "— only pending messages can be rejected."
                    ]
                },
                status=400,
            )
        reason = request.data.get("rejection_reason", "unknown")
        valid_reasons = [choice[0] for choice in Message.REJECTION_REASONS]
        if reason not in valid_reasons:
            return Response(
                {
                    "rejection_reason": [
                        f"Invalid reason. Must be one of: {valid_reasons}"
                    ]
                },
                status=400,
            )
        message.status = "rejected"
        message.rejection_reason = reason
        message.save(update_fields=["status", "rejection_reason"])
        return Response(self.get_serializer(message).data)

    # --- display: approved → displayed ----------------------------------------

    @action(detail=True, methods=["post"])
    def display(self, request, pk=None):  # noqa: ARG002
        message = self.get_object()
        if message.status != "approved":
            return Response(
                {
                    "status": [
                        f"Message is '{message.status}'"
                        "— only approved messages can be displayed."
                    ]
                },
                status=400,
            )
        message.status = "displayed"
        message.displayed_at = datetime.now(tz=UTC)
        message.save(update_fields=["status", "displayed_at"])
        return Response(self.get_serializer(message).data)

    # --- GET /display/: approved messages with since + device filter -----------

    @action(detail=False, methods=["get"], url_path="display")
    def display_messages(self, request):
        messages = Message.objects.filter(status="approved")

        # Optional: filter by creation time
        since = request.query_params.get("since")
        if since:
            messages = messages.filter(created_at__gte=since)

        # Filter out messages already displayed on this device
        device_id = request.headers.get("X-Device-ID")
        if device_id:
            device = DisplayDevice.objects.filter(device_id=device_id).first()
            if device:
                displayed_ids = DisplayLog.objects.filter(device=device).values_list(
                    "message_id", flat=True
                )
                messages = messages.exclude(id__in=displayed_ids)

        page = self.paginate_queryset(messages)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(messages, many=True)
        return Response(serializer.data)

    # --- GET /kpis/: dashboard metrics ----------------------------------------

    @action(detail=False, methods=["get"], url_path="kpis")
    def kpis(self, request):  # noqa: ARG002
        now = timezone.now()
        five_min_ago = now - timedelta(minutes=5)
        settings = Settings.get_settings()

        # Active event
        active_event = Event.objects.filter(
            is_active=True,
            starts_at__lte=now,
            ends_at__gte=now,
        ).first()
        event_info = None
        if active_event:
            remaining = (active_event.ends_at - now).total_seconds()
            event_info = {
                "name": active_event.name,
                "remaining_seconds": round(remaining, 1),
            }

        return Response(
            {
                "pending_count": Message.objects.filter(status="pending").count(),
                "bot_status": settings.bot_status,
                "active_event": event_info,
                "messages_rate": round(
                    Message.objects.filter(created_at__gte=five_min_ago).count() / 5,
                    2,
                ),
            }
        )

    # --- POST /{id}/displayed/: display feedback --------------------------------

    @action(detail=True, methods=["post"], url_path="displayed")
    def mark_displayed(self, request, pk=None):  # noqa: ARG002
        message = self.get_object()
        device_id = request.data.get("device_id")
        if not device_id:
            return Response(
                {"device_id": ["This field is required."]},
                status=400,
            )
        device = DisplayDevice.objects.filter(device_id=device_id).first()
        if not device:
            return Response(
                {"device_id": [f"Unknown device: {device_id}"]},
                status=404,
            )
        DisplayLog.objects.get_or_create(
            message=message,
            device=device,
            defaults={"display_duration_actual": None},
        )
        # Update message.displayed_at if not already set
        if not message.displayed_at:
            message.displayed_at = datetime.now(tz=UTC)
            message.save(update_fields=["displayed_at"])
        return Response({"status": "logged", "device_id": device_id})

    # --- list helpers ---------------------------------------------------------

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


class MessageListView(SingleTableView):
    model = Message
    table_class = MessageTable
    template_name = "streaming/message_list.html"
    context_object_name = "messages"
    paginate_by = 20

    def get_queryset(self):
        return Message.objects.select_related("participant", "event").order_by(
            "-created_at"
        )

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")
        selected = request.POST.getlist("select")  # from checkbox column
        messages = Message.objects.filter(id__in=selected)

        if action == "approve":
            messages.update(status="approved", approved_at=timezone.now())
        elif action == "reject":
            messages.update(status="rejected")
        elif action == "delete":
            messages.delete()

        return self.get(request, *args, **kwargs)


class MessageDetailView(DetailView):
    model = Message
    template_name = "streaming/message_detail.html"
    context_object_name = "message"

    queryset = Message.objects.select_related("participant", "event").all()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        msg = self.object
        badges = [{"label": msg.get_status_display(), "variant": msg.status}]
        ctx["badges"] = badges
        ctx["detail_edit_url"] = None  # Messages are read-only
        ctx["detail_delete_url"] = None  # Messages are read-only
        return ctx


class EventListView(SingleTableView):
    model = Event
    table_class = EventTable
    template_name = "streaming/event_list.html"
    paginate_by = 20

    def get_queryset(self):
        return Event.objects.order_by("starts_at")

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")
        selected = request.POST.getlist("select")
        events = Event.objects.filter(id__in=selected)

        if action == "activate":
            events.update(is_active=True)
        elif action == "deactivate":
            events.update(is_active=False)
        elif action == "delete":
            events.delete()

        return self.get(request, *args, **kwargs)


class EventDetailView(DetailView):
    model = Event

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        action = request.POST.get("action")

        if action == "activate":
            self.object.is_active = True
            self.object.save(update_fields=["is_active"])
        elif action == "deactivate":
            self.object.is_active = False
            self.object.save(update_fields=["is_active"])
        else:
            return HttpResponseBadRequest("Unsupported event action.")

        return self.get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        event = self.object

        badges = [
            {
                "label": "Active" if event.is_active else "Inactive",
                "variant": "active" if event.is_active else "inactive",
            }
        ]
        ctx["badges"] = badges
        ctx["settings"] = Settings.get_settings()
        ctx["event_message_count"] = Message.objects.filter(event=event).count()
        ctx["event_approved_count"] = Message.objects.filter(
            event=event, status="approved"
        ).count()
        ctx["detail_edit_url"] = "streaming:event_edit"
        ctx["detail_delete_url"] = "streaming:event_delete"
        return ctx


class EventUpdateView(UpdateView):
    model = Event
    fields = [
        "name",
        "starts_at",
        "ends_at",
        "is_active",
        "allow_messages",
        "display_mode",
        "scroll_speed_px",
    ]
    template_name = "streaming/event_form.html"

    def get_success_url(self):
        return reverse("streaming:event_list")


class EventCreateView(CreateView):
    model = Event
    fields = [
        "name",
        "starts_at",
        "ends_at",
        "is_active",
        "allow_messages",
        "display_mode",
        "scroll_speed_px",
    ]
    template_name = "streaming/event_form.html"

    def get_success_url(self):
        return reverse("streaming:event_list")


class EventDeleteView(DeleteView):
    model = Event
    template_name = "streaming/event_confirm_delete.html"

    def get_success_url(self):
        return reverse("streaming:event_list")
