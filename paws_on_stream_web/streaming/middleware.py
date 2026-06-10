"""API authentication middleware for static token-based auth."""

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

        # Skip OPTIONS (CORS preflight)
        if request.method == "OPTIONS":
            return self.get_response(request)

        token = request.headers.get("X-API-Token")
        if not token or token != settings.API_AUTH_TOKEN:
            return HttpResponseForbidden(
                '{"error": "Invalid or missing API token"}',
                content_type="application/json",
            )

        return self.get_response(request)
