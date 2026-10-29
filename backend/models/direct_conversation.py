from datetime import datetime, timezone

from extensions import db


class DirectConversation(db.Model):
    __tablename__ = "direct_conversations"

    __table_args__ = (
        db.UniqueConstraint(
            "teacher_id",
            "student_id",
            name="unique_teacher_student_conversation",
        ),
        db.CheckConstraint(
            "teacher_id != student_id",
            name="distinct_direct_conversation_participants",
        ),
    )

    id = db.Column(
        db.Integer,
        primary_key=True,
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

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __init__(
        self,
        teacher_id: int,
        student_id: int,
    ):
        self.teacher_id = teacher_id
        self.student_id = student_id