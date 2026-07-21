from datetime import UTC, datetime

from django.contrib import messages
from django.db import connection
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
from core.forms import SettingsForm, TelegramAccessForm
from core.models import DisplayDevice, DisplayLog, Settings, TelegramAccess
from core.serializers import (
    DisplayDeviceSerializer,
    DisplayLogSerializer,
    SettingsSerializer,
)
from core.tables import DisplayDeviceTable, DisplayLogTable


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
    fields = ["device_id", "hostname", "location", "is_active"]
    template_name = "core/device_form.html"

    def get_success_url(self):
        return reverse("core:device_list")


class DisplayDeviceDeleteView(StaffRequiredMixin, DeleteView):
    model = DisplayDevice
    template_name = "core/device_confirm_delete.html"

    def get_success_url(self):
        return reverse("core:device_list")
