from django.test import SimpleTestCase

from streaming.spam_filters import calculate_spam_score


class SpamFilterTest(SimpleTestCase):
    def test_normal_message_has_no_score(self):
        assert calculate_spam_score("Hallo zusammen") == 0

    def test_repeated_characters_urls_and_uppercase_raise_score(self):
        score = calculate_spam_score("AAAAAAAAAAAAAAAA https://example.com")
        assert score >= 6
