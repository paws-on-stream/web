from django.views.generic import DetailView, ListView
from rest_framework import viewsets

from participants.models import Participant
from participants.serializers import ParticipantCreateSerializer, ParticipantSerializer


class ParticipantViewSet(viewsets.ModelViewSet):
    queryset = Participant.objects.all()

    def get_serializer_class(self):
        if self.action == "create":
            return ParticipantCreateSerializer
        return ParticipantSerializer


class ParticipantListView(ListView):
    queryset = Participant.objects.all()
    context_object_name = "participants"


class ParticipantDetailView(DetailView):
    model = Participant
