"""Message sanitization pipeline for Paws on Stream."""

import re

# Zero-width Unicode characters
ZERO_WIDTH_CHARS = re.compile(r"[\u200b\u200c\u200d\ufeff\u2060]+")

# HTML tags
HTML_TAGS = re.compile(r"<[^>]+>")

# Markdown links: [text](url) -> text
MD_LINKS = re.compile(r"\[([^\]]*)\]\([^\)]*\)")


def sanitize_content(raw: str, max_length: int = 4096) -> str:
    """Clean raw message content for display.

    Steps:
        1. Strip HTML tags.
        2. Remove zero-width characters.
        3. Keep Telegram formatting (*bold*, _italic_, `code`, ~~strike~~).
        4. Collapse markdown links [text](url) -> text.
        5. Truncate to *max_length* characters.
    """
    text = raw.strip() if raw else ""

    # 1. Remove HTML tags
    text = HTML_TAGS.sub("", text)

    # 2. Remove zero-width characters
    text = ZERO_WIDTH_CHARS.sub("", text)

    # 4. Remove markdown links: [text](url) -> text
    text = MD_LINKS.sub(r"\1", text)

    # 5. Truncate
    if len(text) > max_length:
        text = text[:max_length]

    return text
