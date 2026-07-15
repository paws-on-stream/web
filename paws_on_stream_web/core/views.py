from datetime import UTC, datetime

from django.http import HttpResponseBadRequest
from django.urls import reverse
from django.views.generic import DeleteView, DetailView, TemplateView, UpdateView
from django_tables2 import SingleTableView
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.models import DisplayDevice, DisplayLog, Settings
from core.serializers import (
    DisplayDeviceSerializer,
    DisplayLogSerializer,
    SettingsSerializer,
)
from core.tables import DisplayDeviceTable


class SettingsViewSet(viewsets.GenericViewSet):
    serializer_class = SettingsSerializer

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


class DisplayDeviceViewSet(viewsets.ModelViewSet):
    queryset = DisplayDevice.objects.all()
    serializer_class = DisplayDeviceSerializer

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


class SettingsView(TemplateView):
    template_name = "core/settings_detail.html"

    def get_context_data(self, **kwargs):
        settings = Settings.get_settings()
        context = {
            "settings": settings,
        }
        return context


class SettingsUpdateView(UpdateView):
    model = Settings
    fields = [
        "rate_limit_per_minute", "max_message_length", "bot_status",
        "overlay_theme", "overlay_font_size", "auto_approve",
        "display_duration_sec", "reg_api_url", "reg_api_key",
        "status_check_interval", "require_event_active",
        "display_mode", "scroll_speed_px",
    ]
    template_name = "core/settings_form.html"

    def get_object(self, queryset=None):
        return Settings.get_settings()

    def get_success_url(self):
        return reverse("core:settings")


class DisplayDeviceListView(SingleTableView):
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
            return HttpResponseBadRequest("Unsupported device action.")
        if not selected:
            return HttpResponseBadRequest("No devices selected.")

        devices = DisplayDevice.objects.filter(id__in=selected)

        if action == "activate":
            devices.update(is_active=True)
        elif action == "deactivate":
            devices.update(is_active=False)
        else:
            devices.delete()

        return self.get(request, *args, **kwargs)


class DisplayDeviceDetailView(DetailView):
    model = DisplayDevice

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


class DisplayDeviceUpdateView(UpdateView):
    model = DisplayDevice
    fields = ["device_id", "hostname", "location", "is_active"]
    template_name = "core/device_form.html"

    def get_success_url(self):
        return reverse("core:device_list")


class DisplayDeviceDeleteView(DeleteView):
    model = DisplayDevice
    template_name = "core/device_confirm_delete.html"

    def get_success_url(self):
        return reverse("core:device_list")
