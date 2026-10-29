from typing import Any, cast
from datetime import datetime, timezone

import pytest
from marshmallow import ValidationError

from schemas.calendar_event_schema import (
    CreateCalendarEventSchema,
    UpdateCalendarEventSchema,
)


@pytest.fixture()
def calendar_payload():
    return {
        "title": "  Binary practice  ",
        "description": "  Practice conversions.  ",
        "starts_at": "2026-10-07T20:00:00+06:00",
        "ends_at": "2026-10-07T21:00:00+06:00",
        "timezone_name": "  Asia/Dhaka  ",
    }


def test_calendar_create_normalizes_text_and_converts_to_utc(
    calendar_payload,
):
    data = cast(
    dict[str, Any],
    CreateCalendarEventSchema().load(calendar_payload),
)

    assert data["title"] == "Binary practice"
    assert data["description"] == "Practice conversions."
    assert data["timezone_name"] == "Asia/Dhaka"
    assert data["starts_at"] == datetime(
        2026, 10, 7, 14, 0, tzinfo=timezone.utc
    )
    assert data["ends_at"] == datetime(
        2026, 10, 7, 15, 0, tzinfo=timezone.utc
    )
    assert data["starts_at"].tzinfo is timezone.utc
    assert data["ends_at"].tzinfo is timezone.utc

    # Normalization must not modify the caller's payload.
    assert calendar_payload["title"] == "  Binary practice  "


def test_calendar_description_is_optional(calendar_payload):
    del calendar_payload["description"]

    data = cast(
    dict[str, Any],
    CreateCalendarEventSchema().load(calendar_payload),
)

    assert data["description"] == ""


@pytest.mark.parametrize(
    "field",
    ["title", "starts_at", "ends_at", "timezone_name"],
)
def test_calendar_rejects_missing_required_fields(
    calendar_payload, field
):
    del calendar_payload[field]

    with pytest.raises(ValidationError) as error:
        CreateCalendarEventSchema().load(calendar_payload)

    assert field in error.value.messages


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", "   "),
        ("title", "T" * 151),
        ("description", "D" * 2001),
        ("timezone_name", "   "),
        ("timezone_name", "Invalid/Timezone"),
        ("timezone_name", "T" * 101),
        ("starts_at", "not-a-date"),
        ("starts_at", "2026-10-07T20:00:00"),
        ("ends_at", "2026-10-07T21:00:00"),
        ("ends_at", "2026-10-07T20:00:00+06:00"),
        ("ends_at", "2026-10-07T19:00:00+06:00"),
    ],
)
def test_calendar_rejects_invalid_fields(
    calendar_payload, field, value
):
    calendar_payload[field] = value

    with pytest.raises(ValidationError) as error:
        CreateCalendarEventSchema().load(calendar_payload)

    assert field in error.value.messages


@pytest.mark.parametrize(
    "field",
    ["title", "description", "starts_at", "ends_at", "timezone_name"],
)
def test_calendar_rejects_null_fields(calendar_payload, field):
    calendar_payload[field] = None

    with pytest.raises(ValidationError) as error:
        CreateCalendarEventSchema().load(calendar_payload)

    assert field in error.value.messages


@pytest.mark.parametrize("body", [None, [], "event", 42])
def test_calendar_rejects_non_object_input(body):
    with pytest.raises(ValidationError):
        CreateCalendarEventSchema().load(body)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("user_id", 123),
        ("id", "client-chosen-id"),
        ("version", 1),
        ("unexpected", True),
    ],
)
def test_calendar_create_rejects_unknown_fields(
    calendar_payload, field, value
):
    calendar_payload[field] = value

    with pytest.raises(ValidationError) as error:
        CreateCalendarEventSchema().load(calendar_payload)

    assert field in error.value.messages


def test_calendar_compares_times_by_utc_instant(calendar_payload):
    # Local clock values differ, but these represent the same instant.
    calendar_payload["starts_at"] = "2026-10-07T20:00:00+06:00"
    calendar_payload["ends_at"] = "2026-10-07T14:00:00Z"

    with pytest.raises(ValidationError) as error:
        CreateCalendarEventSchema().load(calendar_payload)

    assert "ends_at" in error.value.messages


def test_calendar_accepts_past_event(calendar_payload):
    calendar_payload["starts_at"] = "2020-01-01T10:00:00Z"
    calendar_payload["ends_at"] = "2020-01-01T11:00:00Z"

    data = cast(
    dict[str, Any],
    CreateCalendarEventSchema().load(calendar_payload),
)

    assert data["starts_at"].year == 2020


def test_calendar_update_accepts_full_event_and_version(
    calendar_payload,
):
    calendar_payload["version"] = 3

    data = cast(
    dict[str, Any],
    UpdateCalendarEventSchema().load(calendar_payload),
)

    assert data["version"] == 3
    assert data["title"] == "Binary practice"
    assert data["starts_at"].tzinfo is timezone.utc


def test_calendar_update_requires_version(calendar_payload):
    with pytest.raises(ValidationError) as error:
        UpdateCalendarEventSchema().load(calendar_payload)

    assert "version" in error.value.messages


@pytest.mark.parametrize("version", [0, -1, "1", 1.5, True, None])
def test_calendar_update_rejects_invalid_version(
    calendar_payload, version
):
    calendar_payload["version"] = version

    with pytest.raises(ValidationError) as error:
        UpdateCalendarEventSchema().load(calendar_payload)

    assert "version" in error.value.messages


def test_calendar_update_requires_complete_event():
    with pytest.raises(ValidationError) as error:
        UpdateCalendarEventSchema().load({"version": 1})

    assert set(error.value.messages) == {
        "title",
        "starts_at",
        "ends_at",
        "timezone_name",
    }


def test_calendar_update_rejects_owner_change(calendar_payload):
    calendar_payload.update({
        "version": 1,
        "user_id": 999,
    })

    with pytest.raises(ValidationError) as error:
        UpdateCalendarEventSchema().load(calendar_payload)

    assert "user_id" in error.value.messages