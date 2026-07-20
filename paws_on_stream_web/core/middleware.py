from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import logout
from django.http import HttpResponseRedirect

from core.models import TelegramAccess


class TelegramWhitelistMiddleware:
    """Immediately revoke browser sessions when Telegram access is disabled."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if user.is_authenticated and user.username.startswith("telegram:"):
            access = TelegramAccess.objects.filter(user=user, is_active=True).first()
            if access is None:
                logout(request)
            elif user.is_staff is not True or user.is_superuser != access.is_admin:
                user.is_staff = True
                user.is_superuser = access.is_admin
                user.save(update_fields=("is_staff", "is_superuser"))
        return self.get_response(request)


class DashboardLoginRequiredMiddleware:
    """Require a staff session for every human-facing application page."""

    EXEMPT_PREFIXES = (
        "/admin/",
        "/api/",
        "/auth/",
        "/media/",
        "/metrics/",
        "/static/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(self.EXEMPT_PREFIXES):
            return self.get_response(request)
        if not request.user.is_authenticated or not request.user.is_staff:
            query = urlencode({"next": request.get_full_path()})
            return HttpResponseRedirect(f"{settings.LOGIN_URL}?{query}")
        return self.get_response(request)
