from datetime import datetime, timezone

from extensions import db


class DirectMessage(db.Model):
    __tablename__ = "direct_messages"

    __table_args__ = (
        db.Index(
            "ix_direct_messages_conversation_id_created_at",
            "conversation_id",
            "created_at",
        ),
    )

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    conversation_id = db.Column(
        db.Integer,
        db.ForeignKey("direct_conversations.id"),
        nullable=False,
    )

    sender_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
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

    read_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
    )

    def __init__(
        self,
        conversation_id: int,
        sender_id: int,
        content: str,
    ):
        self.conversation_id = conversation_id
        self.sender_id = sender_id
        self.content = content