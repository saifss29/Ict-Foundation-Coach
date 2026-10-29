from datetime import datetime, timezone
from uuid import uuid4

from extensions import db


class ChatConversation(db.Model):
    __tablename__ = "chat_conversations"

    __table_args__ = (
        db.CheckConstraint(
            "response_language IN ('banglish', 'english')",
            name="valid_chat_conversation_language",
        ),
        db.CheckConstraint(
            "learning_mode IN ('exam_preparation', 'personal_growth')",
            name="valid_chat_conversation_learning_mode",
        ),
    )

    id = db.Column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    title = db.Column(
        db.String(100),
        nullable=False,
    )

    topic = db.Column(
        db.String(100),
        nullable=False,
    )

    response_language = db.Column(
        db.String(10),
        nullable=False,
    )

    learning_mode = db.Column(
        db.String(20),
        nullable=False,
        default="personal_growth",
        server_default="personal_growth",
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
        user_id: int,
        title: str,
        topic: str,
        response_language: str,
        learning_mode: str = "personal_growth",
    ):
        if (
            not isinstance(learning_mode, str)
            or learning_mode not in (
                "exam_preparation",
                "personal_growth",
            )
        ):
            raise ValueError(
                "Learning mode must be exam_preparation "
                "or personal_growth."
            )

        self.user_id = user_id
        self.title = title
        self.topic = topic
        self.response_language = response_language
        self.learning_mode = learning_mode