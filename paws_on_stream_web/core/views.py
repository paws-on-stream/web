import hashlib
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from django.contrib import messages
from django.core.files.base import ContentFile
from django.db import connection, transaction
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import DeleteView, DetailView, TemplateView, UpdateView
from django_tables2 import SingleTableView
from PIL import Image, UnidentifiedImageError
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from core.auth import AdminRequiredMixin, StaffRequiredMixin, StrictStaffRequiredMixin
from core.effective_display import get_effective_display_settings
from core.forms import (
    DisplayDeviceForm,
    SettingsForm,
    TelegramAccessForm,
    ThemeUploadForm,
)
from core.models import (
    DisplayDevice,
    DisplayLog,
    DisplayThemeAsset,
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
from core.themes import (
    MAX_ASSET_BYTES,
    _validate_v3_theme,
    builtin_themes,
    clear_theme_cache,
)


class SettingsViewSet(viewsets.GenericViewSet):
    serializer_class = SettingsSerializer

    def get_throttles(self):
        if self.action in {"retrieve", "effective_display_mode"}:
            return []
        return super().get_throttles()

    @action(detail=False, methods=["get"], url_path="effective-display-mode")
    def effective_display_mode(self, request):  # noqa: ARG002
        app_settings = Settings.get_settings()
        effective = get_effective_display_settings(app_settings)
        return Response(
            {
                "display_mode": effective.display_mode,
                "source": effective.display_mode_source,
                "event_id": effective.event.id if effective.event else None,
            }
        )

    def retrieve(self, request, pk=None):  # noqa: ARG002
        settings = Settings.get_settings()
        serializer = self.get_serializer(settings)
        data = serializer.data
        effective = get_effective_display_settings(settings)
        data["display_mode"] = effective.display_mode
        data["scroll_speed_px"] = effective.scroll_speed_px
        data["display_mode_source"] = effective.display_mode_source
        data["scroll_speed_source"] = effective.scroll_speed_source
        data["event_id"] = effective.event.id if effective.event else None
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
            for k in (
                "hostname", "location", "is_active", "theme_cache_theme",
                "theme_cache_version", "theme_reload_generation",
            )
            if k in request.data
        }
        if "theme_cache_theme" in defaults or "theme_cache_version" in defaults:
            defaults["theme_cache_updated_at"] = datetime.now(tz=UTC)
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
        if action == "push-theme":
            return self._push_theme(request)
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
        return DisplayThemeEditorView._activate_builtin(self, request)

    def _activate_version(self, request):
        return DisplayThemeEditorView._activate_version(self, request)

    def _delete_version(self, request):
        return DisplayThemeEditorView._delete_version(self, request)

    def _push_theme(self, request):
        return DisplayThemeEditorView._push_theme(self, request)


class DisplayThemeEditorView(AdminRequiredMixin, TemplateView):
    template_name = "core/theme_editor.html"

    def get_object(self):
        return get_object_or_404(
            DisplayThemeVersion.objects.prefetch_related("assets"), pk=self.kwargs["pk"]
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        version = self.get_object()
        context["theme_version"] = version
        context["manifest_json"] = kwargs.get(
            "manifest_json", json.dumps(version.manifest, indent=2, ensure_ascii=False)
        )
        return context

    def post(self, request, *args, **kwargs):
        version = self.get_object()
        if version.is_current:
            return HttpResponseBadRequest(
                "Aktive Theme-Versionen dürfen nicht bearbeitet werden."
            )
        action = request.POST.get("action")
        if action == "save-manifest":
            return self._save_manifest(request, version)
        if action == "upload-asset":
            return self._upload_asset(request, version)
        if action == "delete-asset":
            asset = get_object_or_404(version.assets, pk=request.POST.get("asset_id"))
            asset.delete()
            messages.success(request, "Datei wurde entfernt.")
            return redirect(request.path)
        return HttpResponseBadRequest("Unsupported theme editor action.")

    def _save_manifest(self, request, version):
        raw = request.POST.get("manifest", "")
        try:
            manifest = json.loads(raw)
            if not isinstance(manifest, dict):
                raise ValueError("theme.json muss ein JSON-Objekt sein.")
            metadata = manifest.get("theme", {})
            if (
                metadata.get("id") != version.slug
                or metadata.get("version") != version.version
            ):
                raise ValueError(
                    "ID und Version der Theme-Version dürfen nicht geändert werden."
                )
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                for asset in version.assets.all():
                    (root / Path(asset.file.name).name).write_bytes(asset.file.read())
                _validate_v3_theme(manifest, name=version.slug, base_dir=root)
            asset_ids = set(version.assets.values_list("asset_id", flat=True))
            if set(manifest["assets"]) != asset_ids:
                raise ValueError(
                    "Manifest und Dateimanager müssen dieselben Asset-IDs enthalten."
                )
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            messages.error(request, str(exc))
            return self.render_to_response(self.get_context_data(manifest_json=raw))
        version.manifest = manifest
        version.name = manifest["theme"]["name"]
        version.save(update_fields=("manifest", "name"))
        clear_theme_cache()
        messages.success(request, "theme.json wurde validiert und gespeichert.")
        return redirect(request.path)

    def _upload_asset(self, request, version):
        upload = request.FILES.get("file")
        asset_id = str(request.POST.get("asset_key", "")).strip().lower()
        if not upload or not asset_id:
            return HttpResponseBadRequest("Asset-ID und PNG-Datei sind erforderlich.")
        payload = upload.read()
        if len(payload) > MAX_ASSET_BYTES or not upload.name.lower().endswith(".png"):
            return HttpResponseBadRequest("Nur PNG-Dateien bis 5 MB sind erlaubt.")
        try:
            with Image.open(__import__("io").BytesIO(payload)) as image:
                image.verify()
        except (OSError, UnidentifiedImageError):
            return HttpResponseBadRequest("Die Datei ist kein gültiges PNG.")
        asset, _ = DisplayThemeAsset.objects.get_or_create(
            theme_version=version, asset_id=asset_id
        )
        asset.sha256 = hashlib.sha256(payload).hexdigest()
        asset.size = len(payload)
        asset.content_type = "image/png"
        asset.file.save(Path(upload.name).name, ContentFile(payload), save=False)
        asset.save()
        messages.success(
            request, "Datei hochgeladen. Passe jetzt die Metadaten in theme.json an."
        )
        return redirect(request.path)

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

    def _push_theme(self, request):
        settings = Settings.get_settings()
        settings.theme_reload_generation += 1
        settings.save(update_fields=("theme_reload_generation", "updated_at"))
        messages.success(request, "Theme-Reload wurde an alle Displays gesendet.")
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
