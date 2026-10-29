from datetime import datetime, timezone
from typing import Any

from extensions import db


class CalendarEventCreateRequest(db.Model):
    __tablename__ = "calendar_event_create_requests"

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        primary_key=True,
        nullable=False,
    )

    request_id = db.Column(
        db.String(36),
        primary_key=True,
        nullable=False,
    )

    request_hash = db.Column(
        db.String(64),
        nullable=False,
    )

    response_data = db.Column(
        db.JSON,
        nullable=False,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __init__(
        self,
        user_id: int,
        request_id: str,
        request_hash: str,
        response_data: dict[str, Any],
    ):
        self.user_id = user_id
        self.request_id = request_id
        self.request_hash = request_hash
        self.response_data = response_data