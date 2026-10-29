from datetime import datetime, timezone

from extensions import db


class ClassMembership(db.Model):
    __tablename__ = "class_memberships"

    __table_args__ = (
        db.UniqueConstraint(
            "classroom_id",
            "student_id",
            name="unique_student_per_classroom",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)

    classroom_id = db.Column(
        db.Integer,
        db.ForeignKey("classrooms.id"),
        nullable=False,
        index=True,
    )

    student_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    joined_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __init__(
        self,
        classroom_id: int,
        student_id: int,
    ):
        self.classroom_id = classroom_id
        self.student_id = student_id