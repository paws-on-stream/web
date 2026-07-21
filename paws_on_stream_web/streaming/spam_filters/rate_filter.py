from datetime import timedelta

from django.utils import timezone

from streaming.models import Message


class RateFilter:
    def score(self, message, participant) -> float:
        since = timezone.now() - timedelta(seconds=10)
        recent = Message.objects.filter(
            participant=participant, created_at__gte=since
        ).count()
        return 0.2 if recent >= 3 else 0.0
