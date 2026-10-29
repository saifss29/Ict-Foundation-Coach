from datetime import datetime, timezone

from extensions import db


class QuizAssignmentRecipient(db.Model):
    __tablename__ = "quiz_assignment_recipients"

    __table_args__ = (
        db.UniqueConstraint(
            "assignment_id",
            "student_id",
            name="unique_student_per_quiz_assignment",
        ),
    )

    id = db.Column(
        db.Integer,
        primary_key=True,
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
    removed_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __init__(
        self,
        assignment_id: str,
        student_id: int,
    ):
        self.assignment_id = assignment_id
        self.student_id = student_id