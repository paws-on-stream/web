import logging
from datetime import timedelta

from core.auth import StaffRequiredMixin
from django.contrib import messages as django_messages
from django.db.models import Q
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import DeleteView, DetailView, UpdateView
from django_tables2 import SingleTableView
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .forms import ParticipantForm
from .models import Participant
from .reg_sync import (
    RegParticipantNotFound,
    RegSyncError,
    sync_participant_by_telegram_id,
)
from .serializers import ParticipantCreateSerializer, ParticipantSerializer
from .tables import ParticipantTable

logger = logging.getLogger(__name__)


class ParticipantViewSet(viewsets.ModelViewSet):
    queryset = Participant.objects.all()

    def get_serializer_class(self):
        if self.action == "create":
            return ParticipantCreateSerializer
        return ParticipantSerializer

    @action(
        detail=False,
        methods=["post"],
        url_path=r"(?P<telegram_id>\d+)/check_status",
    )
    def check_status(self, request, telegram_id=None):
        participant = Participant.objects.filter(telegram_id=telegram_id).first()
        try:
            participant, changed, created = sync_participant_by_telegram_id(
                int(telegram_id)
            )
        except RegParticipantNotFound as exc:
            if participant is None:
                return Response({"detail": str(exc)}, status=404)
            return Response(
                {
                    "changed": False,
                    "fallback": True,
                    "detail": str(exc),
                    "participant": self.get_serializer(participant).data,
                }
            )
        except RegSyncError as exc:
            if participant is None:
                return Response({"detail": str(exc)}, status=502)
            logger.warning(
                "Reg sync failed for telegram_id=%s, falling back to local status: %s",
                telegram_id,
                exc,
            )
            serializer = self.get_serializer(participant)
            return Response(
                {
                    "changed": False,
                    "fallback": True,
                    "detail": str(exc),
                    "participant": serializer.data,
                }
            )

        serializer = self.get_serializer(participant)
        return Response(
            {"changed": changed, "created": created, "participant": serializer.data},
            status=201 if created else 200,
        )


class ParticipantBanAPIView(APIView):
    def post(self, request, telegram_id):
        participant = Participant.objects.filter(telegram_id=telegram_id).first()
        if not participant:
            return Response(
                {"detail": f"Participant with telegram_id={telegram_id} not found."},
                status=404,
            )

        participant.banned = True
        participant.save(update_fields=["banned"])
        return Response({"status": "ok", "telegram_id": telegram_id})


class ParticipantMuteAPIView(APIView):
    def post(self, request, telegram_id):
        participant = Participant.objects.filter(telegram_id=telegram_id).first()
        if not participant:
            return Response(
                {"detail": f"Participant with telegram_id={telegram_id} not found."},
                status=404,
            )

        try:
            minutes = int(request.data.get("minutes", 0))
        except (TypeError, ValueError):
            return Response(
                {"minutes": ["A whole number of minutes is required."]},
                status=400,
            )
        if minutes <= 0:
            return Response(
                {"minutes": ["Ensure this value is greater than zero."]}, status=400
            )

        participant.muted_until = timezone.now() + timedelta(minutes=minutes)
        participant.save(update_fields=["muted_until"])
        return Response(
            {"status": "ok", "telegram_id": telegram_id, "minutes": minutes}
        )


class ParticipantListView(StaffRequiredMixin, SingleTableView):
    model = Participant
    table_class = ParticipantTable
    template_name = "participants/participant_list.html"
    paginate_by = 20

    def get_queryset(self):
        queryset = Participant.objects.all().order_by("-created_at")

        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(display_name__icontains=query)
                | Q(telegram_id__icontains=query)
                | Q(reg_id__icontains=query)
            )

        checked_in = self.request.GET.get("checked_in", "all")
        if checked_in == "yes":
            queryset = queryset.filter(checked_in=True)
        elif checked_in == "no":
            queryset = queryset.filter(checked_in=False)

        banned = self.request.GET.get("banned", "all")
        if banned == "yes":
            queryset = queryset.filter(banned=True)
        elif banned == "no":
            queryset = queryset.filter(banned=False)

        muted = self.request.GET.get("muted", "all")
        if muted == "yes":
            queryset = queryset.filter(muted_until__isnull=False)
        elif muted == "no":
            queryset = queryset.filter(muted_until__isnull=True)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filters"] = {
            "q": self.request.GET.get("q", "").strip(),
            "checked_in": self.request.GET.get("checked_in", "all"),
            "banned": self.request.GET.get("banned", "all"),
            "muted": self.request.GET.get("muted", "all"),
        }
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")
        selected = request.POST.getlist("select")
        allowed_actions = {"ban", "unban", "delete"}
        if action not in allowed_actions:
            django_messages.error(request, "Bitte eine gültige Aktion auswählen.")
            return redirect("participants:participant_list")
        if not selected:
            django_messages.warning(
                request,
                "Bitte mindestens einen Participant auswählen.",
            )
            return redirect("participants:participant_list")

        participants = Participant.objects.filter(id__in=selected)

        if action == "ban":
            participants.update(banned=True)
            django_messages.success(request, "Ausgewählte Participants wurden gebannt.")
        elif action == "unban":
            participants.update(banned=False, muted_until=None)
            django_messages.success(
                request,
                "Ausgewählte Participants wurden entbannt.",
            )
        else:
            participants.delete()
            django_messages.success(
                request,
                "Ausgewählte Participants wurden gelöscht.",
            )

        return redirect("participants:participant_list")


class ParticipantDetailView(StaffRequiredMixin, DetailView):
    model = Participant

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        action = request.POST.get("action")

        if action == "ban":
            self.object.banned = True
            self.object.save(update_fields=["banned"])
            return redirect(self.object.get_absolute_url())

        if action == "unban":
            self.object.banned = False
            self.object.muted_until = None
            self.object.save(update_fields=["banned", "muted_until"])
            return redirect(self.object.get_absolute_url())

        if action == "mute":
            try:
                minutes = int(request.POST.get("minutes", "15"))
            except (TypeError, ValueError):
                return HttpResponseBadRequest("Mute duration must be an integer.")
            if minutes <= 0:
                return HttpResponseBadRequest(
                    "Mute duration must be greater than zero."
                )

            self.object.muted_until = timezone.now() + timedelta(minutes=minutes)
            self.object.save(update_fields=["muted_until"])
            return redirect(self.object.get_absolute_url())

        if action == "unmute":
            self.object.muted_until = None
            self.object.save(update_fields=["muted_until"])
            return redirect(self.object.get_absolute_url())

        if action == "delete":
            self.object.delete()
            return redirect("participants:participant_list")

        return HttpResponseBadRequest("Unsupported participant action.")

    def get_context_data(self, **kwargs):
        from streaming.models import Message

        ctx = super().get_context_data(**kwargs)
        p = self.object
        is_muted = bool(p.muted_until and p.muted_until > timezone.now())

        badges = []
        if p.banned:
            badges.append({"label": "Banned", "variant": "danger"})
        if is_muted:
            badges.append({"label": "Muted", "variant": "info"})
        if p.checked_in:
            badges.append({"label": "Checked In", "variant": "success"})
        ctx["badges"] = badges
        ctx["is_muted"] = is_muted

        messages = Message.objects.filter(participant=p).order_by("-created_at")
        ctx["recent_messages"] = messages[:10]
        ctx["participant_message_count"] = messages.count()
        ctx["participant_approved_count"] = messages.filter(status="approved").count()
        ctx["participant_rejected_count"] = messages.filter(status="rejected").count()
        ctx["detail_edit_url"] = "participants:participant_edit"
        ctx["detail_delete_url"] = "participants:participant_delete"
        return ctx


class ParticipantUpdateView(StaffRequiredMixin, UpdateView):
    model = Participant
    form_class = ParticipantForm
    template_name = "participants/participant_form.html"

    def get_success_url(self):
        return reverse("participants:participant_list")


class ParticipantDeleteView(StaffRequiredMixin, DeleteView):
    model = Participant
    template_name = "participants/participant_confirm_delete.html"

    def get_success_url(self):
        return reverse("participants:participant_list")
