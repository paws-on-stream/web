"""Small shared counters for API throttling observability."""

from django.core.cache import cache

THROTTLE_ENDPOINTS = (
    "message",
    "media_upload",
    "participant_status",
    "participant_command",
    "other",
)
API_ROLES = ("admin", "bot", "display", "unknown")


def api_role(request) -> str:
    role = getattr(request, "paws_api_role", "unknown")
    return role if role in API_ROLES else "unknown"


def api_endpoint(request) -> str:
    path = request.path
    if path == "/api/v1/message/":
        return "message"
    if path == "/api/v1/media/upload/":
        return "media_upload"
    if path.startswith("/api/v1/participants/") and path.endswith("/check_status/"):
        return "participant_status"
    if path.startswith("/api/v1/participant/"):
        return "participant_command"
    return "other"


def record_throttle_rejection(request) -> None:
    key = f"paws:metrics:throttle:{api_role(request)}:{api_endpoint(request)}"
    cache.add(key, 0, timeout=None)
    cache.incr(key)


def throttle_rejections(role: str, endpoint: str) -> int:
    return int(cache.get(f"paws:metrics:throttle:{role}:{endpoint}", 0))
