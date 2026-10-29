from datetime import datetime, timezone
from uuid import uuid4

from extensions import db


class ClassExam(db.Model):
    __tablename__ = "class_exams"

    __table_args__ = (
        db.CheckConstraint(
            "ends_at > starts_at",
            name="valid_class_exam_dates",
        ),
        db.CheckConstraint(
            "total_marks > 0",
            name="positive_class_exam_total_marks",
        ),
        db.Index(
            "ix_class_exams_classroom_id_starts_at",
            "classroom_id",
            "starts_at",
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

    description = db.Column(
        db.String(2000),
        nullable=False,
        default="",
        server_default="",
    )

    total_marks = db.Column(
        db.Numeric(6, 2),
        nullable=False,
    )

    starts_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
    )

    ends_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
    )

    timezone_name = db.Column(
        db.String(100),
        nullable=False,
    )

    results_published_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
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
        total_marks,
        starts_at: datetime,
        ends_at: datetime,
        timezone_name: str,
        description: str = "",
    ):
        self.classroom_id = classroom_id
        self.title = title
        self.description = description
        self.total_marks = total_marks
        self.starts_at = starts_at
        self.ends_at = ends_at
        self.timezone_name = timezone_name