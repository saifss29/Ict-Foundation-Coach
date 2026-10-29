from datetime import datetime, timezone
from uuid import uuid4

from extensions import db


class WeeklyProgressReport(db.Model):
    __tablename__ = "weekly_progress_reports"

    __table_args__ = (
        db.UniqueConstraint(
            "student_id",
            "delivery_key",
            name="unique_student_weekly_report_delivery",
        ),
        db.CheckConstraint(
            "status IN "
            "('pending', 'ready', 'sending', 'sent', 'failed', 'uncertain')",
            name="valid_weekly_progress_report_status",
        ),
        db.CheckConstraint(
            "period_end > period_start",
            name="valid_weekly_progress_report_period",
        ),
    )

    id = db.Column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    student_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    delivery_key = db.Column(
        db.String(100),
        nullable=False,
    )

    recipient_email = db.Column(
        db.String(255),
        nullable=False,
    )

    period_start = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
    )

    period_end = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
    )

    is_demo = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
        server_default=db.false(),
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    source_data = db.Column(
        db.JSON,
        nullable=True,
    )

    report_text = db.Column(
        db.Text,
        nullable=True,
    )

    error_message = db.Column(
        db.String(500),
        nullable=True,
    )

    generated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
    )

    sending_started_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
    )

    sent_at = db.Column(
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
        student_id: int,
        delivery_key: str,
        recipient_email: str,
        period_start: datetime,
        period_end: datetime,
        is_demo: bool = False,
    ):
        self.student_id = student_id
        self.delivery_key = delivery_key
        self.recipient_email = recipient_email
        self.period_start = period_start
        self.period_end = period_end
        self.is_demo = is_demo
        self.status = "pending"