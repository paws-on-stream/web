from urllib.parse import urlencode

from authlib.integrations.base_client import OAuthError
from authlib.integrations.django_client import OAuth
from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from core.form_utils import ReadableAuthenticationForm
from core.models import TelegramAccess

oauth = OAuth()


def _telegram_client():
    if not settings.TELEGRAM_OIDC_CLIENT_ID or not settings.TELEGRAM_OIDC_CLIENT_SECRET:
        return None
    return oauth.register(
        name="telegram",
        client_id=settings.TELEGRAM_OIDC_CLIENT_ID,
        client_secret=settings.TELEGRAM_OIDC_CLIENT_SECRET,
        server_metadata_url=settings.TELEGRAM_OIDC_DISCOVERY_URL,
        client_kwargs={"scope": "openid profile", "code_challenge_method": "S256"},
    )


def _safe_next(request):
    target = request.POST.get("next") or request.GET.get("next", "/")
    return target if target.startswith("/") and not target.startswith("//") else "/"


def auth_login(request):
    if request.user.is_authenticated:
        return redirect(_safe_next(request))
    next_url = _safe_next(request)
    form = ReadableAuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        if not user.is_staff:
            form.add_error(
                None, "Dieser Account ist nicht für das Dashboard freigeschaltet."
            )
        else:
            login(request, user)
            return redirect(next_url)
    return render(
        request,
        "core/login.html",
        {
            "form": form,
            "next": next_url,
            "telegram_enabled": bool(
                settings.TELEGRAM_OIDC_CLIENT_ID
                and settings.TELEGRAM_OIDC_CLIENT_SECRET
            ),
        },
    )


@require_GET
def telegram_start(request):
    if request.user.is_authenticated:
        return redirect(_safe_next(request))
    client = _telegram_client()
    if client is None:
        return HttpResponse("Telegram login is not configured.", status=503)
    request.session["telegram_login_next"] = _safe_next(request)
    callback = request.build_absolute_uri(reverse("telegram_callback"))
    return client.authorize_redirect(request, callback)


@require_GET
def telegram_callback(request):
    if request.GET.get("error"):
        return HttpResponseBadRequest("Telegram login was cancelled or rejected.")
    client = _telegram_client()
    if client is None:
        return HttpResponse("Telegram login is not configured.", status=503)
    try:
        token = client.authorize_access_token(request)
        claims = token.get("userinfo") or client.parse_id_token(request, token)
        telegram_id = int(claims.get("id") or claims["sub"])
    except (KeyError, OAuthError, TypeError, ValueError):
        return HttpResponseBadRequest("Invalid Telegram identity response.")

    label = claims.get("name", "")[:150]
    access = TelegramAccess.objects.filter(telegram_id=telegram_id).first()
    if telegram_id in settings.TELEGRAM_AUTH_BOOTSTRAP_IDS:
        if access is None:
            access = TelegramAccess.objects.create(
                telegram_id=telegram_id,
                label=label,
                is_active=True,
                is_admin=True,
            )
        elif not access.is_active or not access.is_admin:
            access.is_active = True
            access.is_admin = True
            if not access.label:
                access.label = label
            access.save(update_fields=("is_active", "is_admin", "label", "updated_at"))
    elif access is None:
        access = TelegramAccess.objects.create(
            telegram_id=telegram_id,
            label=label,
            is_active=False,
            is_admin=False,
        )
    elif not access.label and label:
        access.label = label
        access.save(update_fields=("label", "updated_at"))

    if not access.is_active:
        query = urlencode({"telegram_id": telegram_id})
        return HttpResponseRedirect(f"{reverse('telegram_login_denied')}?{query}")

    User = get_user_model()
    user, _ = User.objects.get_or_create(username=f"telegram:{telegram_id}")
    user.first_name = claims.get("given_name", "")[:150]
    user.last_name = claims.get("family_name", "")[:150]
    user.is_active = True
    user.is_staff = True
    user.is_superuser = access.is_admin
    user.set_unusable_password()
    user.save()
    access.user = user
    access.last_login_at = timezone.now()
    if not access.label:
        access.label = claims.get("name", "")[:150]
    access.save(update_fields=("user", "last_login_at", "label", "updated_at"))
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return redirect(request.session.pop("telegram_login_next", "/"))


@require_GET
def telegram_login_denied(request):
    return render(
        request,
        "core/telegram_login_pending.html",
        {"telegram_id": request.GET.get("telegram_id", "")},
        status=403,
    )


@require_POST
def telegram_logout(request):
    logout(request)
    return redirect("login")
