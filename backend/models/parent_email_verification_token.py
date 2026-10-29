from datetime import datetime, timezone

from extensions import db


class ParentEmailVerificationToken(db.Model):
    __tablename__ = "parent_email_verification_tokens"

    __table_args__ = (
        db.CheckConstraint(
            "expires_at > created_at",
            name="valid_parent_email_token_expiry",
        ),
    )

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    student_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    parent_email = db.Column(
        db.String(255),
        nullable=False,
    )

    token_hash = db.Column(
        db.String(64),
        nullable=False,
        unique=True,
    )

    expires_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
    )

    used_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __init__(
        self,
        student_id: int,
        parent_email: str,
        token_hash: str,
        expires_at: datetime,
    ):
        self.student_id = student_id
        self.parent_email = parent_email
        self.token_hash = token_hash
        self.expires_at = expires_at