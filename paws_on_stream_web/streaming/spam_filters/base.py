from typing import Protocol


class SpamFilter(Protocol):
    def score(self, content: str) -> int: ...
