import re

EMOJI = re.compile(
    "["
    "\U0001f300-\U0001f5ff"
    "\U0001f600-\U0001f64f"
    "\U0001f680-\U0001f6ff"
    "\U0001f900-\U0001f9ff"
    "\u2600-\u26ff"
    "\u2700-\u27bf"
    "]"
)


class EmojiSpamFilter:
    def score(self, message, participant) -> float:  # noqa: ARG002
        return 0.3 if len(EMOJI.findall(message.content)) > 10 else 0.0
