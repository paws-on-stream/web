from dataclasses import dataclass

from streaming.spam_filters.base import SpamFilter


@dataclass(frozen=True)
class SpamEvaluation:
    score: float
    evaluated_filters: tuple[str, ...]


def evaluate_spam(
    message,
    participant,
    threshold: float,
    filters: tuple[SpamFilter, ...],
) -> SpamEvaluation:
    total = 0.0
    evaluated = []
    for filter_ in filters:
        evaluated.append(type(filter_).__name__)
        total = min(round(total + filter_.score(message, participant), 2), 1.0)
        if total >= threshold:
            break
    return SpamEvaluation(score=total, evaluated_filters=tuple(evaluated))


def calculate_spam_score(message, participant, threshold: float) -> float:
    from streaming.spam_filters import DEFAULT_FILTERS

    return evaluate_spam(message, participant, threshold, DEFAULT_FILTERS).score
