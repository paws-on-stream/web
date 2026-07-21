from datetime import UTC, datetime

from django.contrib import messages
from django.db import connection, transaction
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import DeleteView, DetailView, TemplateView, UpdateView
from django_tables2 import SingleTableView
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from core.auth import AdminRequiredMixin, StaffRequiredMixin, StrictStaffRequiredMixin
from core.forms import (
    DisplayDeviceForm,
    SettingsForm,
    TelegramAccessForm,
    ThemeUploadForm,
)
from core.models import (
    DisplayDevice,
    DisplayLog,
    DisplayThemeVersion,
    Settings,
    TelegramAccess,
    WebDisplayAccess,
)
from core.serializers import (
    DisplayDeviceSerializer,
    DisplayLogSerializer,
    SettingsSerializer,
)
from core.tables import DisplayDeviceTable, DisplayLogTable
from core.theme_import import ThemeImportError, import_theme_package
from core.themes import builtin_themes, clear_theme_cache


class SettingsViewSet(viewsets.GenericViewSet):
    serializer_class = SettingsSerializer

    def get_throttles(self):
        if self.action == "retrieve":
            return []
        return super().get_throttles()

    def retrieve(self, request, pk=None):  # noqa: ARG002
        settings = Settings.get_settings()
        serializer = self.get_serializer(settings)
        data = serializer.data
        # Strip trailing whitespace / hide empty reg_api_key
        if data.get("reg_api_key"):
            data["reg_api_key"] = data["reg_api_key"].strip()
        return Response(data)

    def update(self, request, pk=None, **kwargs):  # noqa: ARG002
        settings, _ = Settings.objects.get_or_create(id=1)
        serializer = self.get_serializer(settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def partial_update(self, request, pk=None, **kwargs):  # noqa: ARG002
        settings, _ = Settings.objects.get_or_create(id=1)
        serializer = self.get_serializer(settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class HealthAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):  # noqa: ARG002
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception:
            return Response(
                {"status": "degraded", "db_reachable": False},
                status=503,
            )

        return Response({"status": "ok", "db_reachable": True})


class ReadinessAPIView(HealthAPIView):
    pass


class MetricsAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):  # noqa: ARG002
        from participants.models import Participant
        from streaming.models import Message

        counts = {
            status: Message.objects.filter(status=status).count()
            for status in ("pending", "approved", "rejected")
        }
        lines = [
            "# TYPE paws_messages gauge",
            f'paws_messages{{status="pending"}} {counts["pending"]}',
            f'paws_messages{{status="approved"}} {counts["approved"]}',
            f'paws_messages{{status="rejected"}} {counts["rejected"]}',
            "# TYPE paws_participants gauge",
            f"paws_participants {Participant.objects.count()}",
        ]
        return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")


class DisplayDeviceViewSet(viewsets.ModelViewSet):
    queryset = DisplayDevice.objects.all()
    serializer_class = DisplayDeviceSerializer

    def get_throttles(self):
        if self.action == "register":
            return []
        return super().get_throttles()

    @action(detail=False, methods=["post"])
    def register(self, request):  # noqa: ARG002
        device_id = request.data.get("device_id")
        if not device_id:
            return Response(
                {"device_id": ["This field is required."]},
                status=400,
            )
        update_fields = ["last_seen"]
        defaults = {
            k: request.data[k]
            for k in ("hostname", "location", "is_active")
            if k in request.data
        }
        update_fields.extend(defaults.keys())
        device, created = DisplayDevice.objects.update_or_create(
            device_id=device_id,
            defaults=defaults | {"last_seen": datetime.now(tz=UTC)},
        )
        serializer = self.get_serializer(device)
        return Response(serializer.data)


class DisplayLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DisplayLog.objects.select_related("message__participant", "device").all()
    serializer_class = DisplayLogSerializer


class SettingsView(StrictStaffRequiredMixin, TemplateView):
    template_name = "core/settings_detail.html"

    def get_context_data(self, **kwargs):
        settings = Settings.get_settings()
        context = {
            "settings": settings,
        }
        return context


class SettingsUpdateView(StrictStaffRequiredMixin, UpdateView):
    model = Settings
    form_class = SettingsForm
    template_name = "core/settings_form.html"

    def get_object(self, queryset=None):
        return Settings.get_settings()

    def get_success_url(self):
        return reverse("core:settings")


class TelegramAccessListView(AdminRequiredMixin, TemplateView):
    template_name = "core/telegram_access_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["access_entries"] = TelegramAccess.objects.select_related(
            "user"
        ).order_by("is_active", "label", "telegram_id")
        return context


class TelegramAccessUpdateView(AdminRequiredMixin, UpdateView):
    model = TelegramAccess
    form_class = TelegramAccessForm
    template_name = "core/telegram_access_form.html"

    def form_valid(self, form):
        access = self.get_object()
        is_self = access.user_id == self.request.user.pk
        remains_admin = form.cleaned_data["role"] == TelegramAccessForm.ROLE_ADMIN
        if is_self and (not form.cleaned_data["is_active"] or not remains_admin):
            form.add_error(
                None,
                "Du kannst deinen eigenen aktiven Admin-Zugang hier nicht entziehen.",
            )
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        messages.success(self.request, "Telegram-Zugang wurde aktualisiert.")
        return reverse("core:telegram_access_list")


class WebDisplayAccessView(AdminRequiredMixin, TemplateView):
    template_name = "core/web_display_access.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["web_display_access"] = WebDisplayAccess.get_access()
        return context

    def post(self, request, *args, **kwargs):
        access = WebDisplayAccess.get_access()
        action = request.POST.get("action")
        context = self.get_context_data()
        if action == "rotate":
            token = access.rotate()
            context["generated_url"] = (
                request.build_absolute_uri(reverse("web_display")) + f"#{token}"
            )
            messages.success(request, "Ein neuer Monitoring-Link wurde erzeugt.")
        elif action == "revoke":
            access.revoke()
            messages.success(
                request, "Der öffentliche Monitoring-Link wurde widerrufen."
            )
        else:
            return HttpResponseBadRequest("Unsupported web display action.")
        context["web_display_access"] = access
        return self.render_to_response(context)


class DisplayThemeManagementView(AdminRequiredMixin, TemplateView):
    template_name = "core/theme_management.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        app_settings = Settings.get_settings()
        uploaded_versions = list(
            DisplayThemeVersion.objects.select_related("uploaded_by").prefetch_related(
                "assets"
            )
        )
        current_uploaded_slugs = {
            version.slug for version in uploaded_versions if version.is_current
        }
        builtins = builtin_themes()
        for theme in builtins:
            theme["is_active"] = (
                app_settings.overlay_theme == theme["slug"]
                and theme["slug"] not in current_uploaded_slugs
            )
        for version in uploaded_versions:
            version.is_active = (
                version.is_current and app_settings.overlay_theme == version.slug
            )
        context["settings"] = app_settings
        context["builtin_themes"] = builtins
        context["uploaded_versions"] = uploaded_versions
        context.setdefault("upload_form", ThemeUploadForm())
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")
        if action == "upload":
            return self._upload(request)
        if action == "activate-builtin":
            return self._activate_builtin(request)
        if action == "activate-version":
            return self._activate_version(request)
        if action == "delete-version":
            return self._delete_version(request)
        return HttpResponseBadRequest("Unsupported theme action.")

    def _upload(self, request):
        form = ThemeUploadForm(request.POST, request.FILES)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(upload_form=form))
        try:
            version = import_theme_package(
                form.cleaned_data["package"], user=request.user
            )
        except ThemeImportError as exc:
            form.add_error("package", str(exc))
            return self.render_to_response(self.get_context_data(upload_form=form))
        messages.success(request, f"Theme {version} wurde sicher importiert.")
        return redirect("core:theme_management")

    def _activate_builtin(self, request):
        slug = request.POST.get("slug", "")
        if slug not in {item["slug"] for item in builtin_themes()}:
            return HttpResponseBadRequest("Unknown builtin theme.")
        Settings.get_settings()
        with transaction.atomic():
            DisplayThemeVersion.objects.select_for_update().filter(slug=slug).update(
                is_current=False
            )
            app_settings = Settings.objects.select_for_update().get(pk=1)
            app_settings.overlay_theme = slug
            app_settings.save(update_fields=("overlay_theme", "updated_at"))
        clear_theme_cache()
        messages.success(request, f"{slug} ist jetzt für Pi und Web aktiv.")
        return redirect("core:theme_management")

    def _activate_version(self, request):
        try:
            version = DisplayThemeVersion.objects.get(pk=request.POST.get("version_id"))
        except (DisplayThemeVersion.DoesNotExist, ValueError, TypeError):
            return HttpResponseBadRequest("Unknown theme version.")
        Settings.get_settings()
        with transaction.atomic():
            DisplayThemeVersion.objects.select_for_update().filter(
                slug=version.slug
            ).update(is_current=False)
            version.is_current = True
            version.save(update_fields=("is_current",))
            app_settings = Settings.objects.select_for_update().get(pk=1)
            app_settings.overlay_theme = version.slug
            app_settings.save(update_fields=("overlay_theme", "updated_at"))
        clear_theme_cache()
        messages.success(request, f"{version} ist jetzt für Pi und Web aktiv.")
        return redirect("core:theme_management")

    def _delete_version(self, request):
        try:
            version = DisplayThemeVersion.objects.prefetch_related("assets").get(
                pk=request.POST.get("version_id")
            )
        except (DisplayThemeVersion.DoesNotExist, ValueError, TypeError):
            return HttpResponseBadRequest("Unknown theme version.")
        if version.is_current and Settings.get_settings().overlay_theme == version.slug:
            messages.error(
                request, "Eine aktive Theme-Version kann nicht gelöscht werden."
            )
            return redirect("core:theme_management")
        label = str(version)
        for asset in list(version.assets.all()):
            asset.delete()
        version.delete()
        clear_theme_cache()
        messages.success(request, f"{label} wurde gelöscht.")
        return redirect("core:theme_management")


class DisplayDeviceListView(StaffRequiredMixin, SingleTableView):
    model = DisplayDevice
    table_class = DisplayDeviceTable
    template_name = "core/device_list.html"
    paginate_by = 20

    def get_queryset(self):
        return DisplayDevice.objects.all().order_by("device_id")

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")
        selected = request.POST.getlist("select")
        allowed_actions = {"activate", "deactivate", "delete"}
        if action not in allowed_actions:
            messages.error(request, "Bitte eine gültige Aktion auswählen.")
            return redirect("core:device_list")
        if not selected:
            messages.warning(request, "Bitte mindestens ein Device auswählen.")
            return redirect("core:device_list")

        devices = DisplayDevice.objects.filter(id__in=selected)

        if action == "activate":
            devices.update(is_active=True)
            messages.success(request, "Ausgewählte Devices wurden aktiviert.")
        elif action == "deactivate":
            devices.update(is_active=False)
            messages.success(request, "Ausgewählte Devices wurden deaktiviert.")
        else:
            devices.delete()
            messages.success(request, "Ausgewählte Devices wurden gelöscht.")

        return redirect("core:device_list")


class DisplayDeviceDetailView(StaffRequiredMixin, DetailView):
    model = DisplayDevice
    template_name = "core/device_detail.html"

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        action = request.POST.get("action")

        if action == "activate":
            self.object.is_active = True
            self.object.save(update_fields=["is_active"])
            return redirect(self.object.get_absolute_url())
        if action == "deactivate":
            self.object.is_active = False
            self.object.save(update_fields=["is_active"])
            return redirect(self.object.get_absolute_url())
        if action == "delete":
            self.object.delete()
            return redirect("core:device_list")
        return HttpResponseBadRequest("Unsupported device action.")

    def get_context_data(self, **kwargs):
        from core.models import DisplayLog

        ctx = super().get_context_data(**kwargs)
        d = self.object

        badges = [
            {
                "label": "Active" if d.is_active else "Inactive",
                "variant": "success" if d.is_active else "secondary",
            }
        ]
        ctx["badges"] = badges

        ctx["recent_logs"] = DisplayLog.objects.filter(device=d).order_by(
            "-displayed_at"
        )[:10]
        ctx["detail_edit_url"] = "core:device_edit"
        ctx["detail_delete_url"] = "core:device_delete"
        return ctx


class DisplayLogListView(StaffRequiredMixin, SingleTableView):
    model = DisplayLog
    table_class = DisplayLogTable
    template_name = "core/log_list.html"
    paginate_by = 20

    def get_queryset(self):
        return DisplayLog.objects.select_related(
            "message__participant",
            "device",
        ).order_by("-displayed_at")


class DisplayDeviceUpdateView(StaffRequiredMixin, UpdateView):
    model = DisplayDevice
    form_class = DisplayDeviceForm
    template_name = "core/device_form.html"

    def get_success_url(self):
        return reverse("core:device_list")


class DisplayDeviceDeleteView(StaffRequiredMixin, DeleteView):
    model = DisplayDevice
    template_name = "core/device_confirm_delete.html"

    def get_success_url(self):
        return reverse("core:device_list")
