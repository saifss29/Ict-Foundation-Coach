from datetime import datetime, timezone

from extensions import db


class EmailVerificationToken(db.Model):
    __tablename__ = "email_verification_tokens"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    token_hash = db.Column(
        db.String(64),
        nullable=False,
        unique=True,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    expires_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
    )

    used_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
    )

    def __init__(
        self,
        user_id: int,
        token_hash: str,
        expires_at: datetime,
    ):
        self.user_id = user_id
        self.token_hash = token_hash
        self.expires_at = expires_at