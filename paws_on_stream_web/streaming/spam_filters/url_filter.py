import re

URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)


class URLFilter:
    def score(self, message, participant) -> float:  # noqa: ARG002
        return 0.2 if len(URL.findall(message.content)) >= 2 else 0.0
