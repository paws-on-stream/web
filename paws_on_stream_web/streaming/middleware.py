"""API authentication middleware for static token-based auth."""

from hmac import compare_digest

from django.conf import settings
from django.http import HttpResponseForbidden


class ApiTokenMiddleware:
    """
    Require a valid X-API-Token header for all /api/ requests.

    Token is configured via the API_AUTH_TOKEN setting (env var).
    Admin, static files, and non-API paths are excluded.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only enforce on /api/ paths
        if not request.path.startswith("/api/"):
            return self.get_response(request)

        # Allow unauthenticated health checks for liveness probes.
        if request.path in {"/api/v1/health/", "/api/v1/readiness/"}:
            return self.get_response(request)

        # Skip OPTIONS (CORS preflight)
        if request.method == "OPTIONS":
            return self.get_response(request)

        token = request.headers.get("X-API-Token")
        if not token:
            return self._forbidden()

        if settings.API_AUTH_TOKEN and compare_digest(token, settings.API_AUTH_TOKEN):
            return self.get_response(request)
        if settings.BOT_API_AUTH_TOKEN and compare_digest(
            token, settings.BOT_API_AUTH_TOKEN
        ):
            if self._bot_path_allowed(request):
                return self.get_response(request)
            return self._forbidden()
        if settings.DISPLAY_API_AUTH_TOKEN and compare_digest(
            token, settings.DISPLAY_API_AUTH_TOKEN
        ):
            if self._display_path_allowed(request):
                return self.get_response(request)
            return self._forbidden()
        return self._forbidden()

    @staticmethod
    def _bot_path_allowed(request):
        prefixes = (
            "/api/v1/message/",
            "/api/v1/media/upload/",
            "/api/v1/participant/",
            "/api/v1/participants/",
        )
        return request.path.startswith(prefixes)

    @staticmethod
    def _display_path_allowed(request):
        path = request.path
        if request.method == "GET" and (
            path == "/api/v1/messages/display/"
            or path.startswith("/api/v1/settings/")
            or path.startswith("/api/v1/themes/")
        ):
            return True
        return request.method == "POST" and (
            path == "/api/v1/devices/register/"
            or path == "/api/v1/events/killswitch/"
            or (path.startswith("/api/v1/messages/") and path.endswith("/displayed/"))
        )

    @staticmethod
    def _forbidden():
        return HttpResponseForbidden(
            '{"error": "Invalid or missing API token"}',
            content_type="application/json",
        )
