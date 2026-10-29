from datetime import datetime, timedelta, timezone
from uuid import uuid4

from extensions import db


class GeneratedQuiz(db.Model):
    __tablename__ = "generated_quizzes"

    __table_args__ = (
        db.CheckConstraint(
            "response_language IN ('banglish', 'english')",
            name="valid_generated_quiz_language",
        ),
        db.CheckConstraint(
            "learning_mode IN ('exam_preparation', 'personal_growth')",
            name="valid_generated_quiz_learning_mode",
        ),
    )

    id = db.Column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    topic_id = db.Column(
        db.Integer,
        db.ForeignKey("topics.id"),
        nullable=False,
        index=True,
    )

    practice_topic = db.Column(
        db.String(150),
        nullable=True,
    )

    response_language = db.Column(
        db.String(10),
        nullable=False,
    )

    learning_mode = db.Column(
        db.String(20),
        nullable=False,
        default="personal_growth",
        server_default="personal_growth",
    )

    questions = db.Column(
        db.JSON,
        nullable=False,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    expires_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: (
            datetime.now(timezone.utc) + timedelta(minutes=30)
        ),
    )

    attempt_id = db.Column(
        db.Integer,
        db.ForeignKey("quiz_attempts.id"),
        nullable=True,
        unique=True,
    )

    def __init__(
        self,
        user_id: int,
        topic_id: int,
        response_language: str,
        questions: list[dict],
        learning_mode: str = "personal_growth",
        practice_topic: str | None = None,
    ):
        if learning_mode not in (
            "exam_preparation",
            "personal_growth",
        ):
            raise ValueError(
                "Learning mode must be exam_preparation or personal_growth."
            )

        if practice_topic is not None:
            if not isinstance(practice_topic, str):
                raise ValueError(
                    "Practice topic must be text."
                )

            practice_topic = practice_topic.strip()

            if not practice_topic or len(practice_topic) > 150:
                raise ValueError(
                    "Practice topic must be between 1 and 150 characters."
                )

        self.user_id = user_id
        self.topic_id = topic_id
        self.practice_topic = practice_topic
        self.response_language = response_language
        self.learning_mode = learning_mode
        self.questions = questions