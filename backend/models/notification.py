from datetime import datetime, timezone

from extensions import db


class Notification(db.Model):
    __tablename__ = "notifications"

    __table_args__ = (
        db.Index(
            "ix_notifications_user_id_read_at",
            "user_id",
            "read_at",
        ),
    )

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
    )

    notification_type = db.Column(
        db.String(50),
        nullable=False,
    )

    title = db.Column(
        db.String(150),
        nullable=False,
    )

    message = db.Column(
        db.Text,
        nullable=False,
    )

    feedback_id = db.Column(
        db.Integer,
        db.ForeignKey("teacher_feedback.id"),
        nullable=True,
        unique=True,
    )

    direct_message_id = db.Column(
        db.Integer,
        db.ForeignKey("direct_messages.id"),
        nullable=True,
        unique=True,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    read_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
    )

    def __init__(
        self,
        user_id: int,
        notification_type: str,
        title: str,
        message: str,
        feedback_id: int | None = None,
        direct_message_id: int | None = None,
    ):
        self.user_id = user_id
        self.notification_type = notification_type
        self.title = title
        self.message = message
        self.feedback_id = feedback_id
        self.direct_message_id = direct_message_id