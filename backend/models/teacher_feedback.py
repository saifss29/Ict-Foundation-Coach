from datetime import datetime, timezone

from extensions import db


class TeacherFeedback(db.Model):
    __tablename__ = "teacher_feedback"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    classroom_id = db.Column(
        db.Integer,
        db.ForeignKey("classrooms.id"),
        nullable=False,
        index=True,
    )

    teacher_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    student_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    attempt_id = db.Column(
        db.Integer,
        db.ForeignKey("quiz_attempts.id"),
        nullable=True,
        index=True,
    )

    message = db.Column(
        db.Text,
        nullable=False,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __init__(
        self,
        classroom_id: int,
        teacher_id: int,
        student_id: int,
        message: str,
        attempt_id: int | None = None,
    ):
        self.classroom_id = classroom_id
        self.teacher_id = teacher_id
        self.student_id = student_id
        self.message = message
        self.attempt_id = attempt_id