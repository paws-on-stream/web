from datetime import timedelta
from types import SimpleNamespace

from django.test import TestCase
from django.utils import timezone
from participants.factories import ParticipantFactory

from streaming.factories import MessageFactory
from streaming.spam_filters import DEFAULT_FILTERS, calculate_spam_score, evaluate_spam
from streaming.spam_filters.emoji_spam import EmojiSpamFilter
from streaming.spam_filters.length import LengthFilter
from streaming.spam_filters.rate_filter import RateFilter
from streaming.spam_filters.repeat_char import RepeatCharFilter
from streaming.spam_filters.spam_history import ParticipantSpamHistory
from streaming.spam_filters.url_filter import URLFilter


def candidate(content="Hallo zusammen", media_type="text"):
    return SimpleNamespace(content=content, media_type=media_type)


class SpamFilterUnitTest(TestCase):
    def setUp(self):
        self.participant = ParticipantFactory(spam_count=0)

    def test_filter_boundaries(self):
        assert LengthFilter().score(candidate("Hi"), self.participant) == 0.3
        assert LengthFilter().score(candidate("Hey"), self.participant) == 0.0
        assert LengthFilter().score(candidate("", "photo"), self.participant) == 0.0
        assert RepeatCharFilter().score(candidate("aaaaaa"), self.participant) == 0.2
        assert RepeatCharFilter().score(candidate("aaaaa"), self.participant) == 0.0
        assert EmojiSpamFilter().score(candidate("🐾" * 11), self.participant) == 0.3
        assert EmojiSpamFilter().score(candidate("🐾" * 10), self.participant) == 0.0
        assert (
            URLFilter().score(
                candidate("https://one.example https://two.example"), self.participant
            )
            == 0.2
        )
        assert (
            URLFilter().score(candidate("https://one.example"), self.participant) == 0.0
        )

    def test_history_tiers(self):
        expected = {0: 0.0, 1: 0.1, 3: 0.2, 6: 0.3, 10: 0.4, 20: 0.5}
        filter_ = ParticipantSpamHistory()
        for count, score in expected.items():
            self.participant.spam_count = count
            assert filter_.score(candidate(), self.participant) == score

    def test_rate_filter_counts_only_recent_messages_from_same_participant(self):
        old = MessageFactory(participant=self.participant)
        type(old).objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(seconds=11)
        )
        for _ in range(3):
            MessageFactory(participant=self.participant)
        MessageFactory(participant=ParticipantFactory())
        assert RateFilter().score(candidate(), self.participant) == 0.2

    def test_pipeline_short_circuits_at_threshold(self):
        calls = []

        class Filter:
            def __init__(self, score):
                self.value = score

            def score(self, message, participant):  # noqa: ARG002
                calls.append(self.value)
                return self.value

        result = evaluate_spam(
            candidate(), self.participant, 0.7, (Filter(0.3), Filter(0.4), Filter(0.3))
        )
        assert result.score == 0.7
        assert calls == [0.3, 0.4]

    def test_default_pipeline_matches_documented_order(self):
        assert [type(item).__name__ for item in DEFAULT_FILTERS] == [
            "LengthFilter",
            "RepeatCharFilter",
            "EmojiSpamFilter",
            "URLFilter",
            "RateFilter",
            "ParticipantSpamHistory",
        ]
        assert calculate_spam_score(candidate(), self.participant, 0.7) == 0.0
