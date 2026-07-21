import re

REPEATED_CHARACTER = re.compile(r"([^\s])\1{5,}", re.IGNORECASE)


class RepeatCharFilter:
    def score(self, message, participant) -> float:  # noqa: ARG002
        return 0.2 if REPEATED_CHARACTER.search(message.content) else 0.0
