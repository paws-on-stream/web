from datetime import UTC, datetime

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.models import DisplayDevice, DisplayLog, Settings
from core.serializers import (
    DisplayDeviceSerializer,
    DisplayLogSerializer,
    SettingsSerializer,
)


class SettingsViewSet(viewsets.GenericViewSet):
    serializer_class = SettingsSerializer

    def retrieve(self, request, pk=None):  # noqa: ARG002
        settings = Settings.get_settings()
        serializer = self.get_serializer(settings)
        return Response(serializer.data)

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
