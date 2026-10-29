from models.quiz_attempt import QuizAttempt


MASTERY_PRIORITY = {
    "not_started": 0,
    "needs_support": 1,
    "practicing": 2,
    "almost_mastered": 3,
    "mastered": 4,
}


def get_mastery_status(attempts: list[QuizAttempt]) -> str:
    """Attempts must be ordered newest first."""
    if not attempts:
        return "not_started"

    latest = attempts[0]

    if latest.score * 100 < latest.total_questions * 50:
        return "needs_support"

    if latest.score * 100 < latest.total_questions * 80:
        return "practicing"

    if len(attempts) >= 2:
        previous = attempts[1]

        if previous.score * 100 >= previous.total_questions * 80:
            return "mastered"

    return "almost_mastered"