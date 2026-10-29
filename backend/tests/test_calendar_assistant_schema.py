from typing import Any, cast
from uuid import UUID

import pytest
from marshmallow import ValidationError

from schemas.calendar_assistant_schema import CalendarAssistantRequestSchema


EVENT_ID = "d7ef2cb8-f749-4f75-90ed-73cb94f37896"


@pytest.fixture()
def schema():
    return CalendarAssistantRequestSchema()


@pytest.fixture()
def create_payload():
    return {
        "message": "  Kalke Math practice-er event banao  ",
        "timezone_name": "  Asia/Dhaka  ",
        "action": "  create  ",
    }


def test_create_request_is_normalized(schema, create_payload):
    data = cast(dict[str, Any], schema.load(create_payload))

    assert data == {
        "message": "Kalke Math practice-er event banao",
        "timezone_name": "Asia/Dhaka",
        "action": "create",
        "event_id": None,
        "version": None,
    }


def test_update_request_accepts_selected_event(schema, create_payload):
    data = cast(
        dict[str, Any],
        schema.load({
            **create_payload,
            "action": "update",
            "event_id": f"  {EVENT_ID}  ",
            "version": 3,
        }),
    )

    assert data["event_id"] == UUID(EVENT_ID)
    assert data["version"] == 3


@pytest.mark.parametrize(
    "field",
    ["message", "timezone_name", "action"],
)
def test_required_fields_cannot_be_missing(schema, create_payload, field):
    del create_payload[field]

    with pytest.raises(ValidationError):
        schema.load(create_payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("message", " "),
        ("message", "A" * 1001),
        ("message", 123),
        ("message", None),
        ("timezone_name", " "),
        ("timezone_name", "Invalid/Timezone"),
        ("timezone_name", 123),
        ("action", "delete"),
        ("action", None),
        ("event_id", "not-a-uuid"),
        ("version", 0),
        ("version", -1),
        ("version", "1"),
        ("version", True),
        ("version", 1.5),
    ],
)
def test_invalid_fields_are_rejected(
    schema, create_payload, field, value
):
    with pytest.raises(ValidationError):
        schema.load({**create_payload, field: value})


@pytest.mark.parametrize(
    "target",
    [
        {},
        {"event_id": EVENT_ID},
        {"version": 1},
        {"event_id": None, "version": None},
    ],
)
def test_update_requires_event_id_and_version(
    schema, create_payload, target
):
    with pytest.raises(ValidationError):
        schema.load({
            **create_payload,
            "action": "update",
            **target,
        })


@pytest.mark.parametrize(
    "target",
    [
        {"event_id": EVENT_ID},
        {"version": 1},
        {"event_id": EVENT_ID, "version": 1},
    ],
)
def test_create_rejects_update_target(schema, create_payload, target):
    with pytest.raises(ValidationError):
        schema.load({**create_payload, **target})


@pytest.mark.parametrize("body", [None, [], "text", 123])
def test_request_must_be_json_object(schema, body):
    with pytest.raises(ValidationError):
        schema.load(body)


def test_unknown_fields_are_rejected(schema, create_payload):
    with pytest.raises(ValidationError):
        schema.load({**create_payload, "user_id": 999})