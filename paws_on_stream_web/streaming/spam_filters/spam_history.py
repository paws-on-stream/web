class ParticipantSpamHistory:
    def score(self, message, participant) -> float:  # noqa: ARG002
        count = participant.spam_count
        if count >= 20:
            return 0.5
        if count >= 10:
            return 0.4
        if count >= 6:
            return 0.3
        if count >= 3:
            return 0.2
        if count >= 1:
            return 0.1
        return 0.0
