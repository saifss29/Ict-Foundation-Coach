from datetime import datetime, timezone

from extensions import db


class LearningAssignmentRecipient(db.Model):
    __tablename__ = "learning_assignment_recipients"

    __table_args__ = (
        db.UniqueConstraint(
            "assignment_id",
            "student_id",
            name="unique_learning_assignment_student",
        ),
    )

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    assignment_id = db.Column(
        db.String(36),
        db.ForeignKey("learning_assignments.id"),
        nullable=False,
        index=True,
    )

    student_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
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