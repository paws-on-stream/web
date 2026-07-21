from streaming.spam_filters.emoji_spam import EmojiSpamFilter
from streaming.spam_filters.length import LengthFilter
from streaming.spam_filters.pipeline import calculate_spam_score, evaluate_spam
from streaming.spam_filters.rate_filter import RateFilter
from streaming.spam_filters.repeat_char import RepeatCharFilter
from streaming.spam_filters.spam_history import ParticipantSpamHistory
from streaming.spam_filters.url_filter import URLFilter

DEFAULT_FILTERS = (
    LengthFilter(),
    RepeatCharFilter(),
    EmojiSpamFilter(),
    URLFilter(),
    RateFilter(),
    ParticipantSpamHistory(),
)

__all__ = ["DEFAULT_FILTERS", "calculate_spam_score", "evaluate_spam"]
