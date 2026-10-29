from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from extensions import db
from models.calendar_event import CalendarEvent
from models.user import User


@pytest.fixture()
def calendar_owner_id(client):
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Calendar Student",
            "email": "calendar-model@example.com",
            "password": "SecurePass123!",
            "role": "student",
            "academic_level": "hsc",
        },
    )

    assert response.status_code == 201
    return response.get_json()["user"]["id"]


def make_calendar_event(user_id):
    start = datetime.now(timezone.utc)

    return CalendarEvent(
        user_id=user_id,
        title="Binary practice",
        description="Practice binary conversions.",
        starts_at=start,
        ends_at=start + timedelta(hours=1),
        timezone_name="Asia/Dhaka",
    )


def test_calendar_event_persists_fields_and_defaults(
    app, calendar_owner_id
):
    with app.app_context():
        event = make_calendar_event(calendar_owner_id)
        db.session.add(event)
        db.session.commit()

        event_id = event.id
        db.session.expire_all()
        saved = db.session.get(CalendarEvent, event_id)

        assert saved is not None
        assert len(saved.id) == 36
        assert saved.user_id == calendar_owner_id
        assert saved.title == "Binary practice"
        assert saved.description == "Practice binary conversions."
        assert saved.timezone_name == "Asia/Dhaka"
        assert saved.ends_at > saved.starts_at
        assert saved.version == 1
        assert saved.created_at is not None
        assert saved.updated_at is not None


def test_calendar_event_description_defaults_to_empty(
    app, calendar_owner_id
):
    with app.app_context():
        start = datetime.now(timezone.utc)

        event = CalendarEvent(
            user_id=calendar_owner_id,
            title="ICT revision",
            starts_at=start,
            ends_at=start + timedelta(minutes=30),
            timezone_name="Asia/Dhaka",
        )

        db.session.add(event)
        db.session.commit()

        assert event.description == ""


@pytest.mark.parametrize("minutes", [0, -30])
def test_calendar_event_rejects_invalid_date_order(
    app, calendar_owner_id, minutes
):
    with app.app_context():
        event = make_calendar_event(calendar_owner_id)
        event.ends_at = event.starts_at + timedelta(minutes=minutes)
        db.session.add(event)

        with pytest.raises(IntegrityError):
            db.session.commit()

        db.session.rollback()

        assert db.session.scalar(
            db.select(db.func.count()).select_from(CalendarEvent)
        ) == 0


@pytest.mark.parametrize("version", [0, -1])
def test_calendar_event_rejects_nonpositive_version(
    app, calendar_owner_id, version
):
    with app.app_context():
        event = make_calendar_event(calendar_owner_id)
        event.version = version
        db.session.add(event)

        with pytest.raises(IntegrityError):
            db.session.commit()

        db.session.rollback()


@pytest.mark.parametrize(
    "field",
    ["user_id", "title", "starts_at", "ends_at", "timezone_name"],
)
def test_calendar_event_rejects_missing_required_field(
    app, calendar_owner_id, field
):
    with app.app_context():
        event = make_calendar_event(calendar_owner_id)
        setattr(event, field, None)
        db.session.add(event)

        with pytest.raises(IntegrityError):
            db.session.commit()

        db.session.rollback()


def test_calendar_event_rollback_preserves_saved_event(
    app, calendar_owner_id
):
    with app.app_context():
        event = make_calendar_event(calendar_owner_id)
        db.session.add(event)
        db.session.commit()
        event_id = event.id

        event.title = "Changed title"
        event.ends_at = event.starts_at

        with pytest.raises(IntegrityError):
            db.session.commit()

        db.session.rollback()

        saved = db.session.get(CalendarEvent, event_id)
        assert saved is not None
        assert saved.title == "Binary practice"
        assert saved.ends_at > saved.starts_at


def test_calendar_event_owner_reference_and_query_index(app):
    with app.app_context():
        table = db.metadata.tables["calendar_events"]

        owner_foreign_key = next(
            iter(table.c["user_id"].foreign_keys)
        )
        assert owner_foreign_key.column.name == "id"
        assert owner_foreign_key.column.table.name == User.__tablename__

        index = next(
            index
            for index in table.indexes
            if index.name == "ix_calendar_events_user_id_starts_at"
        )
        assert [column.name for column in index.columns] == [
            "user_id",
            "starts_at",
        ]