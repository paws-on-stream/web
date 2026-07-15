from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from participants.factories import ParticipantFactory


class ParticipantListPageFilterTest(TestCase):
    def setUp(self):
        self.alpha = ParticipantFactory(
            display_name="Alpha Fox",
            telegram_id=1111,
            reg_id=101,
            checked_in=True,
            banned=False,
            muted_until=None,
        )
        self.beta = ParticipantFactory(
            display_name="Beta Wolf",
            telegram_id=2222,
            reg_id=202,
            checked_in=False,
            banned=True,
            muted_until=timezone.now() + timedelta(hours=1),
        )
        self.gamma = ParticipantFactory(
            display_name="Gamma Cat",
            telegram_id=3333,
            reg_id=303,
            checked_in=True,
            banned=True,
            muted_until=None,
        )

    def _result_ids(self, response):
        return {obj.id for obj in response.context["table"].data}

    def test_filters_by_search_query(self):
        response = self.client.get("/participants/participants/?q=alpha")
        assert response.status_code == 200
        assert self._result_ids(response) == {self.alpha.id}

    def test_filters_by_telegram_id_query(self):
        response = self.client.get("/participants/participants/?q=2222")
        assert response.status_code == 200
        assert self._result_ids(response) == {self.beta.id}

    def test_filters_checked_in_yes(self):
        response = self.client.get("/participants/participants/?checked_in=yes")
        assert response.status_code == 200
        assert self._result_ids(response) == {self.alpha.id, self.gamma.id}

    def test_filters_banned_no(self):
        response = self.client.get("/participants/participants/?banned=no")
        assert response.status_code == 200
        assert self._result_ids(response) == {self.alpha.id}

    def test_filters_muted_yes(self):
        response = self.client.get("/participants/participants/?muted=yes")
        assert response.status_code == 200
        assert self._result_ids(response) == {self.beta.id}

    def test_combines_filters(self):
        response = self.client.get(
            "/participants/participants/?checked_in=yes&banned=yes&q=gamma"
        )
        assert response.status_code == 200
        assert self._result_ids(response) == {self.gamma.id}

    def test_bulk_action_rejects_unknown_action(self):
        response = self.client.post(
            "/participants/participants/",
            {"action": "nope", "select": [self.alpha.id]},
        )
        assert response.status_code == 400

    def test_bulk_action_rejects_missing_selection(self):
        response = self.client.post(
            "/participants/participants/",
            {"action": "ban"},
        )
        assert response.status_code == 400
