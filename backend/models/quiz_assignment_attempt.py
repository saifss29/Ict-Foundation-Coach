from datetime import datetime, timezone
from uuid import uuid4

from extensions import db


class QuizAssignmentAttempt(db.Model):
    __tablename__ = "quiz_assignment_attempts"

    __table_args__ = (
        db.UniqueConstraint(
            "assignment_id",
            "student_id",
            "attempt_number",
            name="unique_assignment_student_attempt_number",
        ),
        db.CheckConstraint(
            "attempt_number BETWEEN 1 AND 5",
            name="valid_assignment_attempt_number",
        ),
        db.CheckConstraint(
            "expires_at > started_at",
            name="valid_assignment_attempt_expiry",
        ),
        db.CheckConstraint(
            "total_questions BETWEEN 1 AND 20",
            name="valid_assignment_attempt_question_count",
        ),
        db.CheckConstraint(
            "score IS NULL OR "
            "(score >= 0 AND score <= total_questions)",
            name="valid_assignment_attempt_score",
        ),
        db.CheckConstraint(
            "(submitted_at IS NULL AND score IS NULL "
            "AND quiz_attempt_id IS NULL) OR "
            "(submitted_at IS NOT NULL AND score IS NOT NULL "
            "AND quiz_attempt_id IS NOT NULL)",
            name="valid_assignment_attempt_submission",
        ),
        db.CheckConstraint(
            "submitted_at IS NULL OR submitted_at >= started_at",
            name="valid_assignment_attempt_submission_time",
        ),
    )

    id = db.Column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    assignment_id = db.Column(
        db.String(36),
        db.ForeignKey("quiz_assignments.id"),
        nullable=False,
        index=True,
    )

    student_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    attempt_number = db.Column(
        db.Integer,
        nullable=False,
    )

    started_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    expires_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
    )

    answers = db.Column(
        db.JSON,
        nullable=False,
        default=dict,
    )

    total_questions = db.Column(
        db.Integer,
        nullable=False,
    )

    score = db.Column(
        db.Integer,
        nullable=True,
    )

    submitted_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
    )

    quiz_attempt_id = db.Column(
        db.Integer,
        db.ForeignKey("quiz_attempts.id"),
        nullable=True,
        unique=True,
    )

    def __init__(
        self,
        assignment_id: str,
        student_id: int,
        attempt_number: int,
        started_at: datetime,
        expires_at: datetime,
        total_questions: int,
    ):
        self.assignment_id = assignment_id
        self.student_id = student_id
        self.attempt_number = attempt_number
        self.started_at = started_at
        self.expires_at = expires_at
        self.total_questions = total_questions
        self.answers = {}