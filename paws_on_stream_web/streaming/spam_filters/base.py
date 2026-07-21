from typing import Protocol


class SpamFilter(Protocol):
    def score(self, message, participant) -> float: ...
