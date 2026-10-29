from datetime import datetime, timezone

from extensions import db


class ClassExamResult(db.Model):
    __tablename__ = "class_exam_results"

    __table_args__ = (
        db.UniqueConstraint(
            "exam_id",
            "student_id",
            name="unique_class_exam_student",
        ),
        db.CheckConstraint(
            "obtained_marks IS NULL OR obtained_marks >= 0",
            name="nonnegative_class_exam_obtained_marks",
        ),
        db.CheckConstraint(
            "NOT is_absent OR obtained_marks IS NULL",
            name="absent_class_exam_student_has_no_marks",
        ),
    )

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    exam_id = db.Column(
        db.String(36),
        db.ForeignKey("class_exams.id"),
        nullable=False,
        index=True,
    )

    student_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    obtained_marks = db.Column(
        db.Numeric(6, 2),
        nullable=True,
    )

    is_absent = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
        server_default=db.false(),
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
        exam_id: str,
        student_id: int,
    ):
        self.exam_id = exam_id
        self.student_id = student_id
        self.obtained_marks = None
        self.is_absent = False

