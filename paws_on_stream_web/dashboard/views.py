"""Dashboard views for the Paws on Stream admin interface."""

from datetime import timedelta

from core.models import DisplayDevice, Settings
from django.http import HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from participants.models import Participant
from rest_framework.decorators import api_view
from rest_framework.response import Response
from streaming.models import Event, Message
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
    approved_queue = (
        Message.objects.filter(status="approved")
        .select_related("participant", "event", "media_asset")
        .order_by("-approved_at")[:10]
    )
    approved_messages = MessageSerializer(
        approved_queue, many=True, context={"request": request}
    ).data
    for serialized_message, message in zip(
        approved_messages, approved_queue, strict=True
    ):
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
        "approved_messages": approved_messages,
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
