from datetime import datetime, timezone
from uuid import uuid4

from extensions import db


class QuizAssignment(db.Model):
    __tablename__ = "quiz_assignments"

    __table_args__ = (
        db.CheckConstraint(
            "audience IN ('all', 'selected')",
            name="valid_quiz_assignment_audience",
        ),
        db.CheckConstraint(
            "deadline_at > available_at",
            name="valid_quiz_assignment_dates",
        ),
        db.CheckConstraint(
            "time_limit_minutes BETWEEN 1 AND 180",
            name="valid_quiz_assignment_time_limit",
        ),
        db.CheckConstraint(
            "max_attempts BETWEEN 1 AND 5",
            name="valid_quiz_assignment_attempt_limit",
        ),
        db.CheckConstraint(
            "review_at >= deadline_at",
            name="valid_quiz_assignment_review_time",
        ),
    )

    id = db.Column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    quiz_id = db.Column(
        db.String(36),
        db.ForeignKey("teacher_quizzes.id"),
        nullable=False,
        index=True,
    )

    classroom_id = db.Column(
        db.Integer,
        db.ForeignKey("classrooms.id"),
        nullable=False,
        index=True,
    )

    audience = db.Column(
        db.String(10),
        nullable=False,
    )

    available_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
    )

    deadline_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
    )

    time_limit_minutes = db.Column(
        db.Integer,
        nullable=False,
    )

    max_attempts = db.Column(
        db.Integer,
        nullable=False,
        default=1,
        server_default="1",
    )

    review_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
    )



    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __init__(
        self,
        quiz_id: str,
        classroom_id: int,
        audience: str,
        available_at: datetime,
        deadline_at: datetime,
        time_limit_minutes: int,
        review_at: datetime,
        max_attempts: int = 1,
    ):
        self.quiz_id = quiz_id
        self.classroom_id = classroom_id
        self.audience = audience
        self.available_at = available_at
        self.deadline_at = deadline_at
        self.time_limit_minutes = time_limit_minutes
        self.max_attempts = max_attempts
        self.review_at = review_at