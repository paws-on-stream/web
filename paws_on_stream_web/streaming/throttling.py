"""Custom DRF throttling for Paws on Stream."""

from collections.abc import Mapping

from core.api_metrics import record_throttle_rejection
from core.models import Settings
from rest_framework.throttling import SimpleRateThrottle


class UserRateThrottle(SimpleRateThrottle):
    """Per-user rate limiter keyed by telegram_id.

    Defaults to 10 requests/minute but the rate can be overridden in
    DRF settings or on the viewset directly.
    """

    rate = None
    cache_alias = "default"

    def allow_request(self, request, view):  # noqa: ARG002
        # The bot token is a trusted service credential. Its transport calls do
        # not identify an individual participant, so an IP key would throttle
        # the entire bot after a few media uploads. Message creation remains
        # below and is still keyed by telegram_id.
        if (
            getattr(request, "paws_api_role", "") == "bot"
            and request.path != "/api/v1/message/"
        ):
            return True
        allowed = super().allow_request(request, view)
        if not allowed:
            record_throttle_rejection(request)
        return allowed

    def get_rate(self):
        configured = max(Settings.get_settings().rate_limit_per_minute, 1)
        return f"{configured}/min"

    def get_cache_key(self, request, lookup_string):
        # Try authenticated user first
        if request.user and not request.user.is_anonymous:
            return f"pows:ratelimit:user:{request.user.pk}"
        # Fall back to extracting telegram_id from request body (POST /message/)
        telegram_id = (
            request.data.get("telegram_id")
            if isinstance(request.data, Mapping)
            else None
        )
        if telegram_id:
            return f"pows:ratelimit:{telegram_id}"
        # Fallback to IP
        return f"pows:ratelimit:{request.META.get('REMOTE_ADDR', 'unknown')}"


def get_throttle_rate(request):
    """Extract a rate to use based on request body (for POST /message/).

    Returns the telegram_id from the request body so the throttle key
    function can extract it.
    """
    if isinstance(request.data, Mapping):
        telegram_id = request.data.get("telegram_id")
    else:
        telegram_id = None
    return telegram_id
