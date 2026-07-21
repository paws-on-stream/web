import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from participants.factories import ParticipantFactory

from streaming.factories import EventFactory, TextMessageFactory
from streaming.models import Message


class MessageListPageFilterTest(TestCase):
    def setUp(self):
        self.client.force_login(
            get_user_model().objects.create_user("message-filter-staff", is_staff=True)
        )
        Message.objects.all().delete()

        self.participant_alpha = ParticipantFactory(
            display_name="Alpha Filter Target",
            telegram_id=991111001,
        )
        self.participant_beta = ParticipantFactory(
            display_name="Beta Filter Target",
            telegram_id=991111002,
        )
        self.event = EventFactory()

        self.msg_text_pending = TextMessageFactory(
            id=uuid.uuid4(),
            participant=self.participant_alpha,
            event=self.event,
            content="hello-filter-token-alpha",
            raw_content="hello-filter-token-alpha",
            media_type="text",
            status="pending",
        )
        self.msg_photo_approved = TextMessageFactory(
            id=uuid.uuid4(),
            participant=self.participant_beta,
            event=self.event,
            content="",
            raw_content="photo upload",
            media_type="photo",
            status="approved",
        )
        self.msg_sticker_rejected = TextMessageFactory(
            id=uuid.uuid4(),
            participant=self.participant_beta,
            event=self.event,
            content="",
            raw_content="sticker upload",
            media_type="sticker",
            status="rejected",
        )

    def _result_ids(self, response):
        return {obj.id for obj in response.context["object_list"]}

    def test_filters_by_search_content(self):
        response = self.client.get("/streaming/messages/?q=hello-filter-token-alpha")
        assert response.status_code == 200
        result_ids = self._result_ids(response)
        assert result_ids == {self.msg_text_pending.id}, result_ids

    def test_filters_by_search_telegram_id(self):
        response = self.client.get("/streaming/messages/?q=991111002")
        assert response.status_code == 200
        result_ids = self._result_ids(response)
        assert result_ids == {
            self.msg_photo_approved.id,
            self.msg_sticker_rejected.id,
        }, result_ids

    def test_filters_by_status(self):
        response = self.client.get("/streaming/messages/?status=approved")
        assert response.status_code == 200
        result_ids = self._result_ids(response)
        assert result_ids == {self.msg_photo_approved.id}, result_ids

    def test_filters_by_first_display_ack(self):
        self.msg_photo_approved.displayed_at = timezone.now()
        self.msg_photo_approved.save(update_fields=["displayed_at"])

        shown = self.client.get("/streaming/messages/?status=shown")
        not_shown = self.client.get("/streaming/messages/?status=not_shown")

        assert self._result_ids(shown) == {self.msg_photo_approved.id}
        assert self._result_ids(not_shown) == set()

    def test_filters_by_media_type(self):
        response = self.client.get("/streaming/messages/?media_type=sticker")
        assert response.status_code == 200
        result_ids = self._result_ids(response)
        assert result_ids == {self.msg_sticker_rejected.id}, result_ids

    def test_combines_filters(self):
        response = self.client.get(
            "/streaming/messages/?q=beta+filter+target&status=rejected&media_type=sticker"
        )
        assert response.status_code == 200
        result_ids = self._result_ids(response)
        assert result_ids == {self.msg_sticker_rejected.id}, result_ids
