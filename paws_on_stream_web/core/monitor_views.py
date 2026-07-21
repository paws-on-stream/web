import json
import uuid
from datetime import timedelta

from django.conf import settings as django_settings
from django.core import signing
from django.core.cache import cache
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from streaming.models import Message

from core.models import Settings, WebDisplayAccess

COOKIE_NAME = "web_display_access"
COOKIE_MAX_AGE = int(timedelta(days=30).total_seconds())
COOKIE_SALT = "web-display-access-v1"
CURSOR_SALT = "web-display-cursor-v1"
MAX_UUID = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")


def _secure_response(response):
    response["Cache-Control"] = "no-store"
    response["Referrer-Policy"] = "no-referrer"
    response["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; "
        "base-uri 'none'; frame-ancestors 'none'"
    )
    return response


def _cookie_authorized(request):
    value = request.COOKIES.get(COOKIE_NAME)
    if not value:
        return False
    try:
        payload = signing.loads(
            value,
            salt=COOKIE_SALT,
            max_age=COOKIE_MAX_AGE,
        )
    except signing.BadSignature:
        return False
    access = WebDisplayAccess.get_access()
    return access.is_active and str(access.generation) == payload.get("generation")


def _monitor_authorized(request):
    user = request.user
    return bool(user.is_authenticated and user.is_staff) or _cookie_authorized(request)


def _rate_limit_key(request):
    address = request.META.get("REMOTE_ADDR", "unknown")
    return f"web-display-access:{address}"


def _client_rate_limited(request):
    return int(cache.get(_rate_limit_key(request), 0)) >= 10


def _record_failed_attempt(request):
    key = _rate_limit_key(request)
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=60)


def _encode_cursor(at, message_id=MAX_UUID):
    return signing.dumps(
        {"at": at.isoformat(), "id": str(message_id)},
        salt=CURSOR_SALT,
        compress=True,
    )


def _decode_cursor(value):
    try:
        payload = signing.loads(value, salt=CURSOR_SALT, max_age=COOKIE_MAX_AGE)
        at = parse_datetime(payload["at"])
        message_id = uuid.UUID(payload["id"])
    except (KeyError, TypeError, ValueError, signing.BadSignature) as exc:
        raise ValueError("Invalid cursor.") from exc
    if at is None or timezone.is_naive(at):
        raise ValueError("Invalid cursor.")
    return at, message_id


def _message_payload(request, message):
    media_url = ""
    if message.media_asset_id:
        media_url = request.build_absolute_uri(message.media_asset.file.url)
    return {
        "id": str(message.id),
        "display_name": message.participant.display_name,
        "content": message.content,
        "media_type": message.media_type or "text",
        "media_url": media_url,
        "sticker_emoji": message.sticker_emoji,
        "approved_at": message.approved_at.isoformat(),
    }


@require_GET
def web_display(request):
    response = render(
        request,
        "core/web_display.html",
        {
            "access_url": reverse("web_display_access"),
            "feed_url": reverse("web_display_feed"),
        },
    )
    return _secure_response(response)


@csrf_exempt
@require_POST
def web_display_access(request):
    if _client_rate_limited(request):
        return _secure_response(
            JsonResponse({"detail": "Too many attempts."}, status=429)
        )
    try:
        data = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        _record_failed_attempt(request)
        return _secure_response(JsonResponse({"detail": "Invalid JSON."}, status=400))
    access = WebDisplayAccess.get_access()
    if not access.accepts(data.get("token")):
        _record_failed_attempt(request)
        return _secure_response(JsonResponse({"detail": "Invalid token."}, status=403))
    cache.delete(_rate_limit_key(request))
    cookie = signing.dumps(
        {"generation": str(access.generation)},
        salt=COOKIE_SALT,
        compress=True,
    )
    response = JsonResponse({"status": "ok"})
    response.set_cookie(
        COOKIE_NAME,
        cookie,
        max_age=COOKIE_MAX_AGE,
        secure=not django_settings.DEBUG,
        httponly=True,
        samesite="Strict",
        path="/monitor/",
    )
    return _secure_response(response)


@require_GET
def web_display_feed(request):
    if not _monitor_authorized(request):
        return _secure_response(JsonResponse({"detail": "Unauthorized."}, status=401))

    cursor = request.GET.get("cursor", "")
    queryset = Message.objects.filter(
        status="approved",
        approved_at__isnull=False,
    ).select_related("participant", "media_asset")
    now = timezone.now()
    if cursor:
        try:
            after, after_id = _decode_cursor(cursor)
        except ValueError as exc:
            return _secure_response(JsonResponse({"cursor": [str(exc)]}, status=400))
        queryset = queryset.filter(
            Q(approved_at__gt=after) | Q(approved_at=after, id__gt=after_id)
        ).order_by("approved_at", "id")
        messages = list(queryset[:20])
        next_cursor = (
            _encode_cursor(messages[-1].approved_at, messages[-1].id)
            if len(messages) == 20
            else _encode_cursor(now)
        )
    else:
        latest = queryset.order_by("-approved_at", "-id").first()
        messages = [latest] if latest else []
        next_cursor = _encode_cursor(now)

    app_settings = Settings.get_settings()
    response = JsonResponse(
        {
            "messages": [_message_payload(request, item) for item in messages],
            "settings": {
                "display_mode": app_settings.display_mode,
                "display_duration_sec": app_settings.display_duration_sec,
                "scroll_speed_px": app_settings.scroll_speed_px,
                "overlay_font_size": app_settings.overlay_font_size,
                "overlay_theme": app_settings.overlay_theme,
            },
            "cursor": next_cursor,
            "next_poll_after_sec": 3,
        }
    )
    return _secure_response(response)
