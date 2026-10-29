from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from sqlalchemy import select

from extensions import db
from services.email_service import EmailDeliveryError
from services.weekly_report_delivery_service import deliver_weekly_report
from weekly_report_worker import report_schedule, run_report_cycle


NOW = datetime(2026, 10, 12, 6, 0, tzinfo=timezone.utc)
REPORT_TEXT = "Weekly overview\nNo completed quiz activity was recorded."


@pytest.fixture()
def delivery_setup(app, monkeypatch):
    with app.app_context():
        users = db.metadata.tables["users"]

        student_id = db.session.execute(
            users.insert().values(
                name="Delivery Student",
                email="delivery-student@example.com",
                password_hash="test-only",
                role="student",
                academic_level="ssc",
                parent_email="parent@example.com",
                parent_email_verified_at=NOW - timedelta(days=1),
                weekly_report_enabled=True,
            ).returning(users.c.id)
        ).scalar_one()

        db.session.commit()

    generate = Mock(return_value=REPORT_TEXT)
    mail = Mock()

    monkeypatch.setattr(
        "services.weekly_report_delivery_service.generate_weekly_report",
        generate,
    )
    monkeypatch.setattr(
        "services.weekly_report_delivery_service.send_email",
        mail,
    )

    return student_id, generate, mail


def deliver(student_id):
    return deliver_weekly_report(
        student_id=student_id,
        delivery_key="demo:test-slot",
        period_end=NOW,
        is_demo=True,
    )


def saved_report():
    reports = db.metadata.tables["weekly_progress_reports"]

    return db.session.execute(
        select(reports)
    ).mappings().one()


def test_report_sends_once_with_unsubscribe_link(app, delivery_setup):
    student_id, generate, mail = delivery_setup

    with app.app_context():
        assert deliver(student_id) == "sent"
        assert deliver(student_id) == "duplicate"

        generate.assert_called_once()
        mail.assert_called_once()

        message = mail.call_args.kwargs

        assert message["recipient"] == "parent@example.com"
        assert message["subject"] == "[TEST] Weekly Progress Report"
        assert REPORT_TEXT in message["body"]
        assert "automatic delivery every 5 minutes" in message["body"]
        assert "/parent-reports/unsubscribe?token=" in message["body"]

        report = saved_report()
        assert report["status"] == "sent"
        assert report["sent_at"] is not None
        assert report["source_data"] is not None


@pytest.mark.parametrize(
    "changes",
    [
        {"weekly_report_enabled": False},
        {"parent_email_verified_at": None},
        {"parent_email": None},
    ],
)
def test_ineligible_parent_gets_no_report(app, delivery_setup, changes):
    student_id, generate, mail = delivery_setup

    with app.app_context():
        users = db.metadata.tables["users"]

        db.session.execute(
            users.update()
            .where(users.c.id == student_id)
            .values(**changes)
        )
        db.session.commit()

        assert deliver(student_id) == "skipped"
        generate.assert_not_called()
        mail.assert_not_called()


def test_unsubscribe_during_generation_prevents_email(app, delivery_setup):
    student_id, generate, mail = delivery_setup

    def unsubscribe_during_generation(*args, **kwargs):
        users = db.metadata.tables["users"]

        db.session.execute(
            users.update()
            .where(users.c.id == student_id)
            .values(weekly_report_enabled=False)
        )
        db.session.commit()

        return REPORT_TEXT

    generate.side_effect = unsubscribe_during_generation

    with app.app_context():
        assert deliver(student_id) == "skipped"
        mail.assert_not_called()
        assert saved_report()["status"] == "failed"


def test_smtp_failure_is_uncertain_and_not_resent(app, delivery_setup):
    student_id, generate, mail = delivery_setup
    mail.side_effect = EmailDeliveryError("SMTP interrupted")

    with app.app_context():
        assert deliver(student_id) == "uncertain"
        assert deliver(student_id) == "duplicate"

        mail.assert_called_once()
        assert saved_report()["status"] == "uncertain"


def test_demo_schedule_changes_only_at_five_minute_boundary():
    first = report_schedule(NOW + timedelta(seconds=10), "demo")
    same_slot = report_schedule(NOW + timedelta(minutes=4), "demo")
    next_slot = report_schedule(NOW + timedelta(minutes=5), "demo")

    assert first == same_slot
    assert first[0] != next_slot[0]
    assert first[1] == NOW
    assert first[2] is True


def test_weekly_schedule_uses_monday_nine_am_dhaka():
    monday_nine_am = datetime(
        2026, 10, 12, 3, 0, tzinfo=timezone.utc
    )

    key, end, is_demo = report_schedule(monday_nine_am, "weekly")

    assert key == "weekly:2026-10-12"
    assert end == monday_nine_am
    assert is_demo is False

    previous = report_schedule(
        monday_nine_am - timedelta(seconds=1),
        "weekly",
    )
    assert previous[0] == "weekly:2026-10-05"


def test_worker_cycle_does_not_resend_same_slot(app, delivery_setup):
    student_id, generate, mail = delivery_setup

    with app.app_context():
        assert run_report_cycle(NOW, "demo") == {"sent": 1}
        assert run_report_cycle(
            NOW + timedelta(seconds=30),
            "demo",
        ) == {"duplicate": 1}

        generate.assert_called_once()
        mail.assert_called_once()