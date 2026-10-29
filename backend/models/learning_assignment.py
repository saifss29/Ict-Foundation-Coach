from datetime import datetime, timezone
from uuid import uuid4

from extensions import db


class LearningAssignment(db.Model):
    __tablename__ = "learning_assignments"

    __table_args__ = (
        db.CheckConstraint(
            "task_type IN ('written', 'practical')",
            name="valid_learning_assignment_task_type",
        ),
        db.CheckConstraint(
            "audience IN ('all', 'selected')",
            name="valid_learning_assignment_audience",
        ),
        db.CheckConstraint(
            "deadline_at > available_at",
            name="valid_learning_assignment_dates",
        ),
        db.CheckConstraint(
            "total_marks > 0",
            name="positive_learning_assignment_total_marks",
        ),
        db.Index(
            "ix_learning_assignments_classroom_id_available_at",
            "classroom_id",
            "available_at",
        ),
    )

    id = db.Column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    classroom_id = db.Column(
        db.Integer,
        db.ForeignKey("classrooms.id"),
        nullable=False,
    )

    title = db.Column(
        db.String(150),
        nullable=False,
    )

    instructions = db.Column(
        db.Text,
        nullable=False,
    )

    reference_answer = db.Column(
        db.Text,
        nullable=False,
        default="",
        server_default="",
    )

    task_type = db.Column(
        db.String(10),
        nullable=False,
    )

    audience = db.Column(
        db.String(10),
        nullable=False,
    )

    total_marks = db.Column(
        db.Numeric(6, 2),
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

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __init__(
        self,
        classroom_id: int,
        title: str,
        instructions: str,
        task_type: str,
        audience: str,
        total_marks,
        available_at: datetime,
        deadline_at: datetime,
        reference_answer: str = "",
    ):
        self.classroom_id = classroom_id
        self.title = title
        self.instructions = instructions
        self.reference_answer = reference_answer
        self.task_type = task_type
        self.audience = audience
        self.total_marks = total_marks
        self.available_at = available_at
        self.deadline_at = deadline_at