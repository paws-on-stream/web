from django.db.models import Q
from django.http import HttpResponseBadRequest
from django.urls import reverse
from django.views.generic import DeleteView, DetailView, UpdateView
from django_tables2 import SingleTableView
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .forms import ParticipantForm
from .models import Participant
from .reg_sync import RegSyncError, sync_participant_status
from .serializers import ParticipantCreateSerializer, ParticipantSerializer
from .tables import ParticipantTable


class ParticipantViewSet(viewsets.ModelViewSet):
    queryset = Participant.objects.all()

    def get_serializer_class(self):
        if self.action == "create":
            return ParticipantCreateSerializer
        return ParticipantSerializer

    @action(
        detail=False,
        methods=["get"],
        url_path=r"(?P<telegram_id>\d+)/check_status",
    )
    def check_status(self, request, telegram_id=None):
        participant = Participant.objects.filter(telegram_id=telegram_id).first()
        if not participant:
            return Response(
                {"detail": f"Participant with telegram_id={telegram_id} not found."},
                status=404,
            )

        try:
            changed = sync_participant_status(participant)
        except RegSyncError as exc:
            return Response({"detail": str(exc)}, status=502)

        serializer = self.get_serializer(participant)
        return Response({"changed": changed, "participant": serializer.data})


class ParticipantListView(SingleTableView):
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
            return HttpResponseBadRequest("Unsupported participant action.")
        if not selected:
            return HttpResponseBadRequest("No participants selected.")

        participants = Participant.objects.filter(id__in=selected)

        if action == "ban":
            participants.update(banned=True)
        elif action == "unban":
            participants.update(banned=False, muted_until=None)
        else:
            participants.delete()

        return self.get(request, *args, **kwargs)


class ParticipantDetailView(DetailView):
    model = Participant

    def get_context_data(self, **kwargs):
        from streaming.models import Message

        ctx = super().get_context_data(**kwargs)
        p = self.object

        badges = []
        if p.banned:
            badges.append({"label": "Banned", "variant": "danger"})
        if p.muted_until:
            badges.append({"label": "Muted", "variant": "info"})
        if p.checked_in:
            badges.append({"label": "Checked In", "variant": "success"})
        ctx["badges"] = badges

        messages = Message.objects.filter(participant=p).order_by("-created_at")
        ctx["recent_messages"] = messages[:10]
        ctx["participant_message_count"] = messages.count()
        ctx["participant_approved_count"] = messages.filter(status="approved").count()
        ctx["participant_rejected_count"] = messages.filter(status="rejected").count()
        ctx["detail_edit_url"] = "participants:participant_edit"
        ctx["detail_delete_url"] = "participants:participant_delete"
        return ctx


class ParticipantUpdateView(UpdateView):
    model = Participant
    form_class = ParticipantForm
    template_name = "participants/participant_form.html"

    def get_success_url(self):
        return reverse("participants:participant_list")


class ParticipantDeleteView(DeleteView):
    model = Participant
    template_name = "participants/participant_confirm_delete.html"

    def get_success_url(self):
        return reverse("participants:participant_list")
