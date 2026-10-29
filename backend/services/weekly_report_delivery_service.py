from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from uuid import uuid4

from flask import current_app
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from extensions import db
from services.email_service import EmailDeliveryError, send_email
from services.parent_report_token_service import (
    create_parent_unsubscribe_token,
)
from services.weekly_report_ai_service import (
    WeeklyReportGenerationError,
    generate_weekly_report,
)
from services.weekly_report_data_service import collect_weekly_report_data


def eligible_parent(student):
    return (
        student is not None
        and student["role"] == "student"
        and student["academic_level"] in {"ssc", "hsc"}
        and student["weekly_report_enabled"] is True
        and isinstance(student["parent_email"], str)
        and bool(student["parent_email"].strip())
        and student["parent_email_verified_at"] is not None
    )


def save_report_status(report_id, status, **values):
    reports = db.metadata.tables["weekly_progress_reports"]

    db.session.execute(
        reports.update()
        .where(reports.c.id == report_id)
        .values(
            status=status,
            updated_at=datetime.now(timezone.utc),
            **values,
        )
    )
    db.session.commit()


def deliver_weekly_report(
    *,
    student_id: int,
    delivery_key: str,
    period_end: datetime,
    is_demo: bool = False,
) -> str:
    if (
        period_end.tzinfo is None
        or period_end.utcoffset() is None
    ):
        raise ValueError("Report time must include a timezone.")

    if (
        not isinstance(delivery_key, str)
        or not delivery_key
        or len(delivery_key) > 100
    ):
        raise ValueError("Invalid report delivery key.")

    period_end = period_end.astimezone(timezone.utc)
    period_start = period_end - timedelta(days=7)

    users = db.metadata.tables["users"]
    reports = db.metadata.tables["weekly_progress_reports"]

    student = db.session.execute(
        select(users).where(users.c.id == student_id)
    ).mappings().one_or_none()

    if not eligible_parent(student):
        db.session.rollback()
        return "skipped"

    assert student is not None

    original_email = student["parent_email"]
    original_verified_at = student["parent_email_verified_at"]
    student_name = student["name"]
    report_id = str(uuid4())

    # The unique student/key constraint claims this scheduled delivery.
    try:
        db.session.execute(
            reports.insert().values(
                id=report_id,
                student_id=student_id,
                delivery_key=delivery_key,
                recipient_email=original_email,
                period_start=period_start,
                period_end=period_end,
                is_demo=is_demo,
                status="pending",
            )
        )
        db.session.commit()
    except IntegrityError:
        db.session.rollback()

        existing_id = db.session.execute(
            select(reports.c.id).where(
                reports.c.student_id == student_id,
                reports.c.delivery_key == delivery_key,
            )
        ).scalar_one_or_none()

        db.session.rollback()

        if existing_id is not None:
            return "duplicate"

        raise

    try:
        source = collect_weekly_report_data(
            student_id=student_id,
            period_start=period_start,
            period_end=period_end,
        )

        # Do not hold a database transaction during Maira generation.
        db.session.rollback()

        report_text = generate_weekly_report(
            source,
            response_language="banglish",
        )
    except (WeeklyReportGenerationError, ValueError):
        db.session.rollback()
        save_report_status(
            report_id,
            "failed",
            error_message="Progress report generation failed.",
        )
        return "failed"

    save_report_status(
        report_id,
        "ready",
        source_data=source,
        report_text=report_text,
        generated_at=datetime.now(timezone.utc),
    )

    # Commit before SMTP: a crash after this point must not cause a resend.
    save_report_status(
        report_id,
        "sending",
        sending_started_at=datetime.now(timezone.utc),
    )

    # Lock the preference row while sending so unsubscribe and sending
    # have a definite order. SMTP has the existing 15-second timeout.
    student = db.session.execute(
        select(users)
        .where(users.c.id == student_id)
        .with_for_update()
    ).mappings().one_or_none()

    if (
        not eligible_parent(student)
        or student is None
        or student["parent_email"] != original_email
        or student["parent_email_verified_at"] != original_verified_at
    ):
        db.session.rollback()
        save_report_status(
            report_id,
            "failed",
            error_message="Parent consent or email changed before delivery.",
        )
        return "skipped"

    unsubscribe_token = create_parent_unsubscribe_token(
        student_id=student_id,
        parent_email=original_email,
        verified_at=student["parent_email_verified_at"],
    )

    frontend_url = current_app.config["FRONTEND_URL"].rstrip("/")
    unsubscribe_link = (
        f"{frontend_url}/parent-reports/unsubscribe?"
        f"{urlencode({'token': unsubscribe_token})}"
    )

    mode_notice = (
        "TEST MODE: automatic delivery every 5 minutes.\n"
        "This report still covers the last 7 days.\n\n"
        if is_demo
        else ""
    )

    body = (
        "ICT Foundation Coach — Weekly Progress Report\n\n"
        f"Student: {student_name}\n"
        f"Period (UTC): {period_start:%Y-%m-%d %H:%M} "
        f"to {period_end:%Y-%m-%d %H:%M}\n\n"
        f"{mode_notice}"
        f"{report_text}\n\n"
        "This AI-generated summary uses recorded learning activity. "
        "Teacher-reviewed marks remain the assessment results.\n\n"
        "To stop these report emails, open this link and confirm:\n"
        f"{unsubscribe_link}\n"
    )

    try:
        send_email(
            recipient=original_email,
            subject=(
                "[TEST] Weekly Progress Report"
                if is_demo
                else "Weekly Progress Report"
            ),
            body=body,
        )
    except EmailDeliveryError:
        db.session.rollback()

        # SMTP failures can occur after acceptance. Do not auto-resend.
        save_report_status(
            report_id,
            "uncertain",
            error_message=(
                "SMTP delivery could not be confirmed. "
                "Automatic resend is disabled."
            ),
        )
        return "uncertain"
    except Exception:
        db.session.rollback()
        save_report_status(
            report_id,
            "uncertain",
            error_message="Email delivery was interrupted.",
        )
        raise

    save_report_status(
        report_id,
        "sent",
        sent_at=datetime.now(timezone.utc),
        error_message=None,
    )

    return "sent"