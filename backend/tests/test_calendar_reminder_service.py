from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from models.calendar_event import CalendarEvent
from models.notification import Notification
from services.calendar_reminder_service import send_due_calendar_reminders


STARTS_AT = datetime(2026, 10, 7, 14, tzinfo=timezone.utc)


@pytest.fixture()
def reminder_event(app, client):
    def create_event(role="student"):
        registration_data = {
            "name": f"Reminder {role.title()}",
            "email": f"reminder-{role}@example.com",
            "password": "SecurePass123!",
            "role": role,
        }

        if role == "student":
            registration_data["academic_level"] = "hsc"

        response = client.post(
            "/api/auth/register",
            json=registration_data,
        )
        assert response.status_code == 201
        user_id = response.get_json()["user"]["id"]

        with app.app_context():
            event = CalendarEvent(
                user_id=user_id,
                title="Binary practice",
                starts_at=STARTS_AT,
                ends_at=STARTS_AT + timedelta(hours=1),
                timezone_name="Asia/Dhaka",
                reminder_minutes=15,
            )
            db.session.add(event)
            db.session.commit()

            return {
                "id": event.id,
                "user_id": user_id,
            }

    return create_event


@pytest.mark.parametrize("role", ["student", "teacher"])
def test_due_reminder_notifies_event_owner(app, reminder_event, role):
    event = reminder_event(role)
    now = STARTS_AT - timedelta(minutes=15)

    with app.app_context():
        assert send_due_calendar_reminders(now) == 1

        notifications = db.session.scalars(
            db.select(Notification)
        ).all()
        assert len(notifications) == 1

        notification = notifications[0]
        assert notification.user_id == event["user_id"]
        assert notification.notification_type == "calendar_event_reminder"
        assert notification.title == "Upcoming calendar event"
        assert notification.message == (
            '"Binary practice" starts at '
            "07 Oct 2026, 08:00 PM (Asia/Dhaka)."
        )
        assert notification.read_at is None

        saved = db.session.get(CalendarEvent, event["id"])
        assert saved is not None
        assert saved.reminder_sent_at is not None
        assert saved.reminder_sent_at.replace(tzinfo=timezone.utc) == now


@pytest.mark.parametrize(
    ("offset", "expected"),
    [
        (timedelta(minutes=-16), 0),
        (timedelta(minutes=-14), 1),
        (timedelta(), 0),
        (timedelta(minutes=1), 0),
    ],
)
def test_reminder_respects_due_time_and_event_start(
    app, reminder_event, offset, expected
):
    event = reminder_event()

    with app.app_context():
        assert send_due_calendar_reminders(STARTS_AT + offset) == expected

        assert db.session.scalar(
            db.select(db.func.count()).select_from(Notification)
        ) == expected

        saved = db.session.get(CalendarEvent, event["id"])
        assert saved is not None
        assert (saved.reminder_sent_at is not None) == bool(expected)


def test_repeated_processing_does_not_duplicate_reminder(app, reminder_event):
    event = reminder_event()
    first_run = STARTS_AT - timedelta(minutes=15)

    with app.app_context():
        assert send_due_calendar_reminders(first_run) == 1
        assert send_due_calendar_reminders(
            first_run + timedelta(minutes=1)
        ) == 0

        assert db.session.scalar(
            db.select(db.func.count()).select_from(Notification)
        ) == 1

        saved = db.session.get(CalendarEvent, event["id"])
        assert saved is not None
        assert saved.reminder_sent_at is not None
        assert saved.reminder_sent_at.replace(
            tzinfo=timezone.utc
        ) == first_run


def test_disabled_reminder_is_skipped(app, reminder_event):
    event = reminder_event()

    with app.app_context():
        saved = db.session.get(CalendarEvent, event["id"])
        assert saved is not None
        saved.reminder_minutes = None
        db.session.commit()

        assert send_due_calendar_reminders(
            STARTS_AT - timedelta(minutes=10)
        ) == 0

        assert db.session.scalar(
            db.select(db.func.count()).select_from(Notification)
        ) == 0

        db.session.refresh(saved)
        assert saved.reminder_sent_at is None


def test_failed_reminder_transaction_rolls_back_and_can_retry(
    app, reminder_event, monkeypatch
):
    event = reminder_event()
    now = STARTS_AT - timedelta(minutes=15)

    with app.app_context():
        real_flush = db.session.flush

        def fail_commit():
            real_flush()
            raise SQLAlchemyError("Test failure")

        with monkeypatch.context() as patch:
            patch.setattr(db.session, "commit", fail_commit)

            with pytest.raises(SQLAlchemyError):
                send_due_calendar_reminders(now)

        assert db.session.scalar(
            db.select(db.func.count()).select_from(Notification)
        ) == 0

        saved = db.session.get(CalendarEvent, event["id"])
        assert saved is not None
        assert saved.reminder_sent_at is None

        assert send_due_calendar_reminders(now) == 1
        assert db.session.scalar(
            db.select(db.func.count()).select_from(Notification)
        ) == 1


def test_naive_processing_time_is_rejected(app, monkeypatch):
    commit = Mock()

    with app.app_context():
        monkeypatch.setattr(db.session, "commit", commit)

        with pytest.raises(ValueError):
            send_due_calendar_reminders(datetime(2026, 10, 7, 13, 45))

        commit.assert_not_called()