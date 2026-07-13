from django_tables2 import SingleTableView
from django.views.generic import DetailView
from rest_framework import viewsets

from participants.models import Participant
from participants.serializers import ParticipantCreateSerializer, ParticipantSerializer
from participants.tables import ParticipantTable


class ParticipantViewSet(viewsets.ModelViewSet):
    queryset = Participant.objects.all()

    def get_serializer_class(self):
        if self.action == "create":
            return ParticipantCreateSerializer
        return ParticipantSerializer


class ParticipantListView(SingleTableView):
    model = Participant
    table_class = ParticipantTable
    template_name = "participants/participant_list.html"
    paginate_by = 20

    def get_queryset(self):
        return Participant.objects.all().order_by("-created_at")

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")
        selected = request.POST.getlist("select")
        participants = Participant.objects.filter(id__in=selected)

        if action == "ban":
            participants.update(banned=True)
        elif action == "unban":
            participants.update(banned=False, muted_until=None)
        elif action == "delete":
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
        return ctx
