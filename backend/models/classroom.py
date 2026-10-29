from datetime import datetime, timezone

from extensions import db


class Classroom(db.Model):
    __tablename__ = "classrooms"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(
        db.String(100),
        nullable=False,
    )

    teacher_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    join_code = db.Column(
        db.String(12),
        nullable=False,
        unique=True,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __init__(
        self,
        name: str,
        teacher_id: int,
        join_code: str,
    ):
        self.name = name
        self.teacher_id = teacher_id
        self.join_code = join_code