import hashlib
from datetime import UTC, datetime, timedelta
from io import BytesIO

from core.auth import StaffRequiredMixin
from core.models import DisplayDevice, DisplayLog, Settings
from django.contrib import messages
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponseBadRequest
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.generic import CreateView, DeleteView, DetailView, UpdateView
from django_tables2 import SingleTableView
from participants.models import Participant
from PIL import Image, UnidentifiedImageError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from streaming.models import DisplayEvent, Event, MediaAsset, Message
from streaming.sanitization import sanitize_content
from streaming.serializers import EventSerializer, MessageSerializer
from streaming.spam_filters import calculate_spam_score
from streaming.tables import EventTable, MessageTable


def _absolute_media_url(request, file_url: str) -> str:
    if file_url.startswith(("http://", "https://")):
        return file_url
    normalized = f"/{file_url.lstrip('/')}"
    return request.build_absolute_uri(normalized)


class EventViewSet(viewsets.ModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer

    def perform_create(self, serializer):
        with transaction.atomic():
            if serializer.validated_data.get("is_active"):
                Event.objects.filter(is_active=True).update(is_active=False)
            serializer.save()

    def perform_update(self, serializer):
        with transaction.atomic():
            if serializer.validated_data.get("is_active"):
                Event.objects.exclude(pk=serializer.instance.pk).update(is_active=False)
            serializer.save()


class MessageViewSet(viewsets.ModelViewSet):
    queryset = Message.objects.select_related(
        "participant", "event", "media_asset"
    ).all()
    serializer_class = MessageSerializer

    def get_throttles(self):
        if getattr(self, "action", None) in {"display_messages", "mark_displayed"}:
            return []
        return super().get_throttles()

    # --- create: sanitization + auto-approve ---------------------------------

    def create(self, request, *args, **kwargs):
        settings = Settings.get_settings()
        data = request.data.copy()
        raw_content = data.get("raw_content", data.get("content", "")).strip()
        media_type = data.get("media_type", "text")
        content = sanitize_content(raw_content, max_length=settings.max_message_length)
        for protected_field in (
            "status",
            "spam_score",
            "rejection_reason",
            "approved_by",
            "approved_at",
            "displayed_at",
        ):
            data.pop(protected_field, None)

        if media_type == "text" and not content:
            return Response(
                {"content": ["Message is empty after sanitization."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        participant = None
        participant_id = data.get("participant_id")
        telegram_id = data.get("telegram_id")
        if participant_id:
            participant = Participant.objects.filter(id=participant_id).first()
        elif telegram_id:
            participant = Participant.objects.filter(telegram_id=telegram_id).first()
            if participant:
                data["participant_id"] = participant.id

        if not participant:
            return Response(
                {
                    "status": "rejected",
                    "reason": "unknown",
                    "message": "Participant not found.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if participant.banned:
            return Response(
                {
                    "status": "rejected",
                    "reason": "banned",
                    "message": "Participant is banned.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if participant.muted_until and participant.muted_until > timezone.now():
            return Response(
                {
                    "status": "rejected",
                    "reason": "muted",
                    "message": "Participant is currently muted.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not participant.effective_checked_in:
            return Response(
                {
                    "status": "rejected",
                    "reason": "not_checkedin",
                    "message": "Participant is not checked in.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if settings.bot_status != "online":
            return Response(
                {
                    "status": "rejected",
                    "reason": "offline",
                    "message": "Bot is offline.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if settings.require_event_active:
            now = timezone.now()
            active_event = Event.objects.filter(
                is_active=True,
                allow_messages=True,
                starts_at__lte=now,
                ends_at__gte=now,
            ).first()
            if not active_event:
                return Response(
                    {
                        "status": "rejected",
                        "reason": "no_event",
                        "message": "No active event.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            data["event"] = active_event.id

        media_asset_id = data.get("media_asset_id")
        if media_asset_id:
            media_asset = MediaAsset.objects.filter(id=media_asset_id).first()
            if not media_asset:
                return Response(
                    {
                        "status": "rejected",
                        "reason": "unknown",
                        "message": "Media asset not found.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if media_type not in {"photo", "gif", "sticker"}:
                return Response(
                    {"media_type": ["A media asset requires photo, gif, or sticker."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if media_asset.media_type != media_type:
                return Response(
                    {"media_asset_id": ["Asset media_type does not match message."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            data.pop("media_url", None)
        elif media_type != "text":
            return Response(
                {"media_asset_id": ["This field is required for media messages."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        else:
            data.pop("media_url", None)

        data["content"] = content
        data["raw_content"] = raw_content
        spam_score = calculate_spam_score(content)

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        message = serializer.save(spam_score=spam_score)
        if settings.auto_approve and spam_score <= settings.spam_threshold:
            message.status = "approved"
            message.approved_at = timezone.now()
            message.save(update_fields=["status", "approved_at"])
        return Response(
            self.get_serializer(message).data,
            status=status.HTTP_201_CREATED,
        )

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
            since_value = parse_datetime(since)
            if since_value is None or timezone.is_naive(since_value):
                return Response(
                    {"since": ["A timezone-aware ISO datetime is required."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            messages = messages.filter(created_at__gte=since_value)

        limit = request.query_params.get("limit")
        if limit:
            try:
                self.paginator.page_size = max(1, min(int(limit), 100))
            except (TypeError, ValueError):
                return Response(
                    {"limit": ["A valid integer is required."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

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
        duration_actual = request.data.get("display_duration_actual")
        if not device_id:
            return Response(
                {"device_id": ["This field is required."]},
                status=400,
            )
        if duration_actual is not None:
            try:
                duration_actual = int(duration_actual)
            except (TypeError, ValueError):
                return Response(
                    {"display_duration_actual": ["A valid integer is required."]},
                    status=400,
                )
            if duration_actual < 0:
                return Response(
                    {"display_duration_actual": ["Ensure this value is >= 0."]},
                    status=400,
                )
        device = DisplayDevice.objects.filter(device_id=device_id).first()
        if not device:
            return Response(
                {"device_id": [f"Unknown device: {device_id}"]},
                status=404,
            )
        DisplayLog.objects.update_or_create(
            message=message,
            device=device,
            defaults={"display_duration_actual": duration_actual},
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


class MessageListView(StaffRequiredMixin, SingleTableView):
    model = Message
    table_class = MessageTable
    template_name = "streaming/message_list.html"
    context_object_name = "messages"
    paginate_by = 20

    def get_queryset(self):
        queryset = Message.objects.select_related(
            "participant", "event", "media_asset"
        ).order_by("-created_at")

        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(content__icontains=query)
                | Q(raw_content__icontains=query)
                | Q(participant__display_name__icontains=query)
                | Q(participant__telegram_id__icontains=query)
            )

        status_filter = self.request.GET.get("status", "all")
        if status_filter in {"pending", "approved", "rejected", "displayed"}:
            queryset = queryset.filter(status=status_filter)

        media_filter = self.request.GET.get("media_type", "all")
        if media_filter in {"text", "photo", "gif", "sticker"}:
            queryset = queryset.filter(media_type=media_filter)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filters"] = {
            "q": self.request.GET.get("q", "").strip(),
            "status": self.request.GET.get("status", "all"),
            "media_type": self.request.GET.get("media_type", "all"),
        }
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")
        selected = request.POST.getlist("select")  # from checkbox column
        allowed_actions = {"approve", "reject", "delete"}
        if action not in allowed_actions:
            messages.error(request, "Bitte eine gültige Aktion auswählen.")
            return redirect("streaming:message_list")
        if not selected:
            messages.warning(request, "Bitte mindestens eine Nachricht auswählen.")
            return redirect("streaming:message_list")

        selected_messages = Message.objects.filter(id__in=selected)

        if action == "approve":
            selected_messages.update(status="approved", approved_at=timezone.now())
            messages.success(request, "Ausgewählte Nachrichten wurden freigegeben.")
        elif action == "reject":
            selected_messages.update(status="rejected")
            messages.success(request, "Ausgewählte Nachrichten wurden abgelehnt.")
        else:
            selected_messages.delete()
            messages.success(request, "Ausgewählte Nachrichten wurden gelöscht.")

        return redirect("streaming:message_list")


class MessageDetailView(StaffRequiredMixin, DetailView):
    model = Message
    template_name = "streaming/message_detail.html"
    context_object_name = "message"

    queryset = Message.objects.select_related(
        "participant", "event", "media_asset"
    ).all()

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        action = request.POST.get("action")

        if action == "approve":
            if self.object.status == "pending":
                self.object.status = "approved"
                self.object.approved_at = timezone.now()
                self.object.save(update_fields=["status", "approved_at"])
            return redirect(self.object.get_absolute_url())

        if action == "reject":
            if self.object.status == "pending":
                self.object.status = "rejected"
                if not self.object.rejection_reason:
                    self.object.rejection_reason = "unknown"
                self.object.save(update_fields=["status", "rejection_reason"])
            return redirect(self.object.get_absolute_url())

        if action == "delete":
            self.object.delete()
            return redirect("streaming:message_list")

        return HttpResponseBadRequest("Unsupported message action.")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        msg = self.object
        badges = [{"label": msg.get_status_display(), "variant": msg.status}]
        ctx["badges"] = badges
        ctx["detail_edit_url"] = None  # Messages are read-only
        ctx["detail_delete_url"] = None  # Messages are read-only
        return ctx


class EventListView(StaffRequiredMixin, SingleTableView):
    model = Event
    table_class = EventTable
    template_name = "streaming/event_list.html"
    paginate_by = 20

    def get_queryset(self):
        return Event.objects.order_by("starts_at")

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")
        selected = request.POST.getlist("select")
        allowed_actions = {"activate", "deactivate", "delete"}
        if action not in allowed_actions:
            messages.error(request, "Bitte eine gültige Aktion auswählen.")
            return redirect("streaming:event_list")
        if not selected:
            messages.warning(request, "Bitte mindestens ein Event auswählen.")
            return redirect("streaming:event_list")

        events = Event.objects.filter(id__in=selected)

        if action == "activate":
            if events.count() != 1:
                messages.error(request, "Es kann nur ein Event aktiviert werden.")
                return redirect("streaming:event_list")
            event = events.get()
            Event.objects.exclude(pk=event.pk).update(is_active=False)
            event.is_active = True
            event.save(update_fields=["is_active"])
            messages.success(request, "Ausgewählte Events wurden aktiviert.")
        elif action == "deactivate":
            events.update(is_active=False)
            messages.success(request, "Ausgewählte Events wurden deaktiviert.")
        else:
            events.delete()
            messages.success(request, "Ausgewählte Events wurden gelöscht.")

        return redirect("streaming:event_list")


class EventDetailView(StaffRequiredMixin, DetailView):
    model = Event

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        action = request.POST.get("action")

        if action == "activate":
            Event.objects.exclude(pk=self.object.pk).update(is_active=False)
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


class EventUpdateView(StaffRequiredMixin, UpdateView):
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


class EventCreateView(StaffRequiredMixin, CreateView):
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


class EventDeleteView(StaffRequiredMixin, DeleteView):
    model = Event
    template_name = "streaming/event_confirm_delete.html"

    def get_success_url(self):
        return reverse("streaming:event_list")


class MediaUploadAPIView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        upload = request.FILES.get("file")
        if not upload:
            return Response(
                {"file": ["This field is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if upload.size > 10 * 1024 * 1024:
            return Response(
                {"file": ["File exceeds the 10 MB limit."]},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        if upload.content_type != "image/webp":
            return Response(
                {"file": ["Content-Type must be image/webp."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payload = upload.read()
        try:
            image = Image.open(BytesIO(payload))
            if image.format != "WEBP":
                raise ValueError("not webp")
            width, height = image.size
            frame_count = int(getattr(image, "n_frames", 1))
            duration_ms = 0
            has_alpha = False
            for frame_index in range(frame_count):
                image.seek(frame_index)
                image.load()
                duration_ms += max(0, int(image.info.get("duration", 0)))
                has_alpha = (
                    has_alpha
                    or "A" in image.getbands()
                    or (image.mode == "P" and "transparency" in image.info)
                )
            image.verify()
        except (UnidentifiedImageError, OSError, ValueError, EOFError):
            return Response(
                {"file": ["Uploaded content is not a valid WebP image."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if width > 1280 or height > 1280:
            return Response(
                {"file": ["WebP dimensions must not exceed 1280x1280."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if frame_count > 150:
            return Response(
                {"file": ["Animated WebP must not exceed 150 frames."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if duration_ms > 10_000:
            return Response(
                {"file": ["Animated WebP must not exceed 10 seconds."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        upload.seek(0)

        media_type = request.data.get("media_type", "").strip()
        valid_types = {choice[0] for choice in MediaAsset.MEDIA_TYPES}
        if media_type not in valid_types:
            return Response(
                {
                    "media_type": [
                        f"Invalid media_type. Must be one of: {sorted(valid_types)}"
                    ]
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        telegram_file_id = request.data.get("telegram_file_id", "").strip()
        telegram_file_unique_id = request.data.get(
            "telegram_file_unique_id", ""
        ).strip()
        sticker_emoji = request.data.get("sticker_emoji", "").strip()
        if not telegram_file_id or not telegram_file_unique_id:
            return Response(
                {
                    "telegram_file_id": ["This field is required."],
                    "telegram_file_unique_id": ["This field is required."],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        source_filename = upload.name or ""

        defaults = {
            "file": ContentFile(
                payload, name=f"{hashlib.sha256(payload).hexdigest()}.webp"
            ),
            "media_type": media_type,
            "telegram_file_id": telegram_file_id,
            "sticker_emoji": sticker_emoji,
            "source_filename": source_filename,
            "format": "webp",
            "animated": frame_count > 1,
            "width": width,
            "height": height,
            "duration_ms": duration_ms,
            "frame_count": frame_count,
            "has_alpha": has_alpha,
            "sha256": hashlib.sha256(payload).hexdigest(),
        }

        asset = MediaAsset.objects.filter(
            telegram_file_unique_id=telegram_file_unique_id
        ).first()
        if asset and asset.sha256 != defaults["sha256"]:
            return Response(
                {
                    "telegram_file_unique_id": [
                        "Identifier already belongs to different content."
                    ]
                },
                status=status.HTTP_409_CONFLICT,
            )
        if asset is None:
            asset = MediaAsset.objects.filter(sha256=defaults["sha256"]).first()
        created = asset is None
        if created:
            asset = MediaAsset.objects.create(
                telegram_file_unique_id=telegram_file_unique_id, **defaults
            )

        return Response(
            {
                "media_asset_id": asset.id,
                "media_url": _absolute_media_url(request, asset.file.url),
                "status": "stored",
                "media_format": asset.format,
                "media_animated": asset.animated,
                "media_width": asset.width,
                "media_height": asset.height,
                "media_duration_ms": asset.duration_ms,
                "media_frame_count": asset.frame_count,
                "media_has_alpha": asset.has_alpha,
                "sha256": asset.sha256,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


def media_asset_content(request, file_name):  # noqa: ARG001
    storage_name = f"media_assets/{file_name}"
    asset = MediaAsset.objects.filter(file=storage_name).first()
    if asset is None:
        raise Http404
    response = FileResponse(asset.file.open("rb"), content_type="image/webp")
    response["Cache-Control"] = "public, max-age=31536000, immutable"
    response["X-Content-Type-Options"] = "nosniff"
    return response


class DisplayEventAPIView(APIView):
    def get_throttles(self):
        return []

    def post(self, request):
        device_id = str(request.data.get("device_id", "")).strip()
        device = DisplayDevice.objects.filter(device_id=device_id).first()
        if not device:
            return Response({"device_id": ["Unknown device."]}, status=404)
        event_type = str(request.data.get("event_type", "")).strip()
        if event_type not in {value for value, _ in DisplayEvent.EVENT_TYPES}:
            return Response({"event_type": ["Invalid display event type."]}, status=400)
        occurred_at = request.data.get("occurred_at")
        parsed = parse_datetime(str(occurred_at)) if occurred_at else None
        if parsed is None or timezone.is_naive(parsed):
            return Response(
                {"occurred_at": ["A timezone-aware ISO datetime is required."]},
                status=400,
            )
        event = DisplayEvent.objects.create(
            device=device, event_type=event_type, occurred_at=parsed
        )
        return Response({"id": event.id, "status": "stored"}, status=201)
