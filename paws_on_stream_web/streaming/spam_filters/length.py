class LengthFilter:
    def score(self, message, participant) -> float:  # noqa: ARG002
        content = message.content.strip()
        if not content and message.media_type != "text":
            return 0.0
        return 0.3 if len(content) < 3 else 0.0
