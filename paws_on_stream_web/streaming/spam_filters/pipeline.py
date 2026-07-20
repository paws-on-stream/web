import re

REPEATED_CHAR = re.compile(r"(.)\1{7,}", re.IGNORECASE)
URL = re.compile(r"https?://|www\.", re.IGNORECASE)


class RepeatedCharacterFilter:
    def score(self, content: str) -> int:
        return min(len(REPEATED_CHAR.findall(content)) * 3, 9)


class UrlFilter:
    def score(self, content: str) -> int:
        return min(len(URL.findall(content)) * 3, 9)


class UppercaseFilter:
    def score(self, content: str) -> int:
        letters = [char for char in content if char.isalpha()]
        if len(letters) < 12:
            return 0
        ratio = sum(char.isupper() for char in letters) / len(letters)
        return 3 if ratio > 0.8 else 0


DEFAULT_FILTERS = (RepeatedCharacterFilter(), UrlFilter(), UppercaseFilter())


def calculate_spam_score(content: str) -> int:
    return sum(filter_.score(content) for filter_ in DEFAULT_FILTERS)
