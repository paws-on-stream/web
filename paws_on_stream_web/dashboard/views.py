"""Dashboard views for the Paws on Stream admin interface."""

import hashlib
import io
import uuid
from datetime import timedelta

from core.models import DisplayDevice, Settings
from django.core.files.base import ContentFile
from django.http import HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST
from participants.models import Participant
from PIL import Image, ImageDraw
from rest_framework.decorators import api_view
from rest_framework.response import Response
from streaming.models import Event, MediaAsset, Message
from streaming.serializers import MessageSerializer


def _apply_dashboard_message_action(message: Message, action: str) -> None:
    if action == "approve":
        if message.status != "pending":
            raise ValueError("Only pending messages can be approved.")
        message.status = "approved"
        message.approved_at = timezone.now()
        message.approved_by = None
        message.save(update_fields=["status", "approved_at", "approved_by"])
        return

    if action == "reject":
        if message.status != "pending":
            raise ValueError("Only pending messages can be rejected.")
        message.status = "rejected"
        message.rejection_reason = "moderator_other"
        message.save(update_fields=["status", "rejection_reason"])
        return

    raise ValueError(f"Unsupported dashboard action: {action}")


def _create_test_media(media_type: str) -> MediaAsset:
    """Create a small valid WebP asset for a display pipeline test."""
    colors = {
        "photo": (39, 130, 204, 255),
        "gif": (143, 63, 191, 255),
        "sticker": (26, 143, 92, 0),
    }
    image = Image.new("RGBA", (480, 270), colors[media_type])
    draw = ImageDraw.Draw(image)
    draw.rectangle((16, 16, 464, 254), outline=(255, 255, 255, 255), width=6)
    draw.text((42, 112), f"TEST {media_type.upper()}", fill=(255, 255, 255, 255))
    payload = io.BytesIO()
    animated = media_type == "gif"
    if animated:
        second = Image.new("RGBA", (480, 270), (236, 142, 34, 255))
        second_draw = ImageDraw.Draw(second)
        second_draw.text((42, 112), "TEST GIF", fill=(255, 255, 255, 255))
        image.save(
            payload,
            format="WEBP",
            save_all=True,
            append_images=[second],
            duration=500,
            loop=0,
            lossless=True,
        )
    else:
        image.save(payload, format="WEBP", lossless=True)
    identifier = uuid.uuid4().hex
    asset = MediaAsset(
        media_type=media_type,
        telegram_file_id=f"admin-test-{identifier}",
        telegram_file_unique_id=f"admin-test-{identifier}",
        sticker_emoji="🐾" if media_type == "sticker" else "",
        source_filename=f"admin-test-{media_type}.webp",
        format="webp",
        animated=animated,
        width=480,
        height=270,
        duration_ms=1000 if animated else 0,
        frame_count=2 if animated else 1,
        has_alpha=media_type == "sticker",
    )
    content = payload.getvalue()
    asset.sha256 = hashlib.sha256(content).hexdigest()
    asset.file.save(f"admin-test-{identifier}.webp", ContentFile(content), save=False)
    asset.save()
    return asset


@require_POST
def dashboard_test_message(request):
    """Inject an approved test message into the ordinary display queue."""
    if not request.user.is_authenticated or not request.user.is_superuser:
        return HttpResponseForbidden("Admin login required.")
    media_type = request.POST.get("media_type", "")
    if media_type not in {"text", "photo", "gif", "sticker"}:
        return HttpResponseBadRequest("Unsupported test media type.")
    participant, _ = Participant.objects.get_or_create(
        telegram_id=0,
        defaults={"display_name": "Display-Test", "checked_in": True},
    )
    now = timezone.now()
    asset = _create_test_media(media_type) if media_type != "text" else None
    labels = {"text": "Text", "photo": "Foto", "gif": "GIF", "sticker": "Sticker"}
    message = Message.objects.create(
        participant=participant,
        content=f"Display-Testnachricht: {labels[media_type]}",
        raw_content=f"Display-Testnachricht: {labels[media_type]}",
        media_type=media_type,
        media_asset=asset,
        sticker_emoji="🐾" if media_type == "sticker" else "",
        status="approved",
        approved_at=now,
        approved_by=request.user,
    )
    return JsonResponse({"status": "ok", "message_id": str(message.pk)})


def dashboard(request):
    """Main dashboard page."""
    now = timezone.now()
    five_min_ago = now - timedelta(minutes=5)

    if request.method == "POST":
        if not request.user.is_authenticated or not request.user.is_staff:
            return HttpResponseForbidden("Staff login required.")
        message_id = request.POST.get("message_id")
        action = request.POST.get("action")
        if not message_id or not action:
            return HttpResponseBadRequest("Missing message_id or action.")

        message = get_object_or_404(Message, pk=message_id)
        try:
            _apply_dashboard_message_action(message, action)
        except ValueError as exc:
            return HttpResponseBadRequest(str(exc))

        if "application/json" in request.headers.get("Accept", ""):
            return JsonResponse({"status": "ok", "message_id": str(message.pk)})

        return redirect(reverse("dashboard:dashboard"))

    pending_count = Message.objects.filter(status="pending").count()
    messages_rate = round(
        Message.objects.filter(created_at__gte=five_min_ago).count() / 5, 1
    )

    # active_event = Event.objects.filter(
    #     is_active=True, starts_at__lte=now, ends_at__gte=now
    # ).first()
    # active_event_data = None
    # if active_event:
    #     remaining = (active_event.ends_at - now).total_seconds() / 60
    #     active_event_data = {
    #         "name": active_event.name,
    #         "remaining_minutes": round(remaining),
    #     }

    recent_messages = Message.objects.filter(status="pending").select_related(
        "participant"
    )[:20]

    kpis = [
        {
            "name": "Pending Messages",
            "id": "msg-pending",
            "value": pending_count,
        },
        {
            "name": "Messages Rate",
            "id": "msg-rate",
            "value": messages_rate,
        },
        {
            "name": "Participants",
            "id": "participants",
            "value": Participant.objects.all().count(),
        },
    ]

    context = {
        "kpis": kpis,
        "recent_messages": recent_messages,
        "api_token": request.META.get("API_AUTH_TOKEN", ""),
    }
    return render(request, "dashboard/dashboard.html", context)


def _dashboard_payload(request):
    now = timezone.now()
    five_min_ago = now - timedelta(minutes=5)
    settings = Settings.get_settings()
    active_event = Event.objects.filter(
        is_active=True, starts_at__lte=now, ends_at__gte=now
    ).first()
    queue = (
        Message.objects.filter(status="pending")
        .select_related("participant", "event", "media_asset")
        .order_by("-created_at")[:50]
    )
    messages = MessageSerializer(
        queue, many=True, context={"request": request}
    ).data
    for serialized_message, message in zip(messages, queue, strict=True):
        serialized_message["event_name"] = message.event.name if message.event else ""

    return {
        "kpis": {
            "pending_count": Message.objects.filter(status="pending").count(),
            "approved_count": Message.objects.filter(status="approved").count(),
            "displayed_count": Message.objects.filter(
                displayed_at__isnull=False
            ).count(),
            "rejected_count": Message.objects.filter(status="rejected").count(),
            "messages_per_minute": round(
                Message.objects.filter(created_at__gte=five_min_ago).count() / 5, 1
            ),
            "participants": Participant.objects.count(),
            "bot_status": settings.bot_status,
            "auto_approve": settings.auto_approve,
            "active_event": (
                {
                    "name": active_event.name,
                    "remaining_minutes": round(
                        (active_event.ends_at - now).total_seconds() / 60
                    ),
                }
                if active_event
                else None
            ),
        },
        "messages": messages,
        "updated_at": now.isoformat(),
    }


@require_GET
@never_cache
def dashboard_live(request):
    """Staff-only live moderation queue and KPI data."""
    if not request.user.is_authenticated or not request.user.is_staff:
        return HttpResponseForbidden("Staff login required.")
    return JsonResponse(_dashboard_payload(request))


def messages_page(request):
    """Messages review page."""
    status = request.GET.get("status", "pending")
    messages = (
        Message.objects.filter(status=status)
        .select_related("participant", "event")
        .order_by("-created_at")[:50]
    )
    context = {
        "messages": MessageSerializer(messages, many=True).data,
        "current_status": status,
        "api_token": request.META.get("API_AUTH_TOKEN", ""),
    }
    return render(request, "dashboard/messages.html", context)


def participants_page(request):
    """Participants list page."""
    from participants.models import Participant
    from participants.serializers import ParticipantSerializer

    query = request.GET.get("q", "")
    participants = Participant.objects.all()
    if query:
        participants = participants.filter(display_name__icontains=query)
    context = {
        "participants": ParticipantSerializer(participants, many=True).data,
        "search_query": query,
        "api_token": request.META.get("API_AUTH_TOKEN", ""),
    }
    return render(request, "dashboard/participants.html", context)


def events_page(request):
    """Events list page."""
    from streaming.serializers import EventSerializer

    events = Event.objects.all()
    context = {
        "events": EventSerializer(events, many=True).data,
        "api_token": request.META.get("API_AUTH_TOKEN", ""),
    }
    return render(request, "dashboard/events.html", context)


def devices_page(request):
    """Display devices list page."""
    from core.serializers import DisplayDeviceSerializer

    devices = DisplayDevice.objects.all()
    context = {
        "devices": DisplayDeviceSerializer(devices, many=True).data,
        "api_token": request.META.get("API_AUTH_TOKEN", ""),
    }
    return render(request, "dashboard/devices.html", context)


def settings_page(request):
    """Settings page."""
    from core.serializers import SettingsSerializer

    settings = Settings.get_settings()
    context = {
        "settings": SettingsSerializer(settings).data,
        "api_token": request.META.get("API_AUTH_TOKEN", ""),
    }
    return render(request, "dashboard/settings.html", context)


# --- KPI endpoint (JSON) --------------------------------------------------
@api_view(["GET"])
def kpi_endpoint(request):
    """Return current dashboard KPIs as JSON for API consumers."""
    now = timezone.now()
    five_min_ago = now - timedelta(minutes=5)
    settings = Settings.get_settings()

    active_event = Event.objects.filter(
        is_active=True, starts_at__lte=now, ends_at__gte=now
    ).first()

    kpis = {
        "bot_status": settings.bot_status,
        "auto_approve": settings.auto_approve,
        "pending_count": Message.objects.filter(status="pending").count(),
        "approved_count": Message.objects.filter(status="approved").count(),
        "displayed_count": Message.objects.filter(displayed_at__isnull=False).count(),
        "rejected_count": Message.objects.filter(status="rejected").count(),
        "messages_per_minute": round(
            Message.objects.filter(created_at__gte=five_min_ago).count() / 5, 1
        ),
    }

    if active_event:
        remaining = (active_event.ends_at - now).total_seconds() / 60
        kpis["active_event"] = {
            "name": active_event.name,
            "remaining_minutes": round(remaining),
        }

    return Response(kpis)
