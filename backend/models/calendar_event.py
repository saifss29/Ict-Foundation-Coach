from datetime import datetime, timezone
from uuid import uuid4

from extensions import db


class CalendarEvent(db.Model):
    __tablename__ = "calendar_events"

    __table_args__ = (
        db.CheckConstraint(
            "ends_at > starts_at",
            name="valid_calendar_event_dates",
        ),
        db.CheckConstraint(
            "version >= 1",
            name="positive_calendar_event_version",
        ),
        db.Index(
            "ix_calendar_events_user_id_starts_at",
            "user_id",
            "starts_at",
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
    )

    title = db.Column(
        db.String(150),
        nullable=False,
    )

    description = db.Column(
        db.String(2000),
        nullable=False,
        default="",
        server_default="",
    )

    starts_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
    )

    ends_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
    )

    timezone_name = db.Column(
        db.String(100),
        nullable=False,
    )

    version = db.Column(
        db.Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    reminder_minutes = db.Column(
        db.Integer,
        nullable=True,
        default=15,
        server_default="15",
    )

    reminder_sent_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
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
        starts_at: datetime,
        ends_at: datetime,
        timezone_name: str,
        description: str = "",
        reminder_minutes: int | None = 15,
    ):
        self.user_id = user_id
        self.title = title
        self.description = description
        self.starts_at = starts_at
        self.ends_at = ends_at
        self.timezone_name = timezone_name
        self.version = 1
        self.reminder_minutes = reminder_minutes
        self.reminder_sent_at = None