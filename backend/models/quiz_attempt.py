from datetime import datetime, timezone

from extensions import db


class QuizAttempt(db.Model):
    __tablename__ = "quiz_attempts"
    __table_args__ = (
        db.CheckConstraint(
            "score >= 0 AND score <= total_questions",
            name="valid_quiz_score",
        ),
        db.CheckConstraint(
            "total_questions > 0",
            name="positive_total_questions",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
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
    score = db.Column(db.Integer, nullable=False)
    total_questions = db.Column(db.Integer, nullable=False)
    completed_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __init__(
        self,
        user_id: int,
        topic_id: int,
        score: int,
        total_questions: int,
    ):
        self.user_id = user_id
        self.topic_id = topic_id
        self.score = score
        self.total_questions = total_questions