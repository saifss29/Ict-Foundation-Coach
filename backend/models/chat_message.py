from datetime import datetime, timezone

from extensions import db


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"

    __table_args__ = (
        db.CheckConstraint(
            "role IN ('student', 'assistant')",
            name="valid_chat_message_role",
        ),
    )

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    conversation_id = db.Column(
        db.String(36),
        db.ForeignKey("chat_conversations.id"),
        nullable=False,
        index=True,
    )

    role = db.Column(
        db.String(10),
        nullable=False,
    )

    content = db.Column(
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
        conversation_id: str,
        role: str,
        content: str,
    ):
        self.conversation_id = conversation_id
        self.role = role
        self.content = content