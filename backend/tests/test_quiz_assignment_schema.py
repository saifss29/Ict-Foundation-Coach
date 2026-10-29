from datetime import datetime, timezone

import pytest
from marshmallow import ValidationError

from schemas.quiz_assignment_schema import CreateQuizAssignmentSchema


@pytest.fixture()
def valid_assignment_payload():
    return {
        "quiz_id": "12345678-1234-4234-8234-123456789abc",
        "classroom_id": 1,
        "audience": "all",
        "available_at": "2026-10-06T10:00:00+06:00",
        "deadline_at": "2026-10-06T11:00:00+06:00",
        "time_limit_minutes": 30,
        "review_at": "2026-10-06T11:00:00+06:00",
    }


def test_assignment_defaults_and_utc_conversion(
    valid_assignment_payload,
):
    data = CreateQuizAssignmentSchema().load(
        valid_assignment_payload
    )

    assert isinstance(data, dict)
    assert data["student_ids"] == []
    assert data["max_attempts"] == 1
    assert data["quiz_id"] == valid_assignment_payload["quiz_id"]
    assert data["available_at"] == datetime(
        2026, 10, 6, 4, 0, tzinfo=timezone.utc
    )
    assert data["deadline_at"] == datetime(
        2026, 10, 6, 5, 0, tzinfo=timezone.utc
    )
    assert data["review_at"] == data["deadline_at"]
    assert data["available_at"].tzinfo == timezone.utc


def test_assignment_accepts_selected_students(
    valid_assignment_payload,
):
    valid_assignment_payload.update({
        "audience": "selected",
        "student_ids": [2, 3],
    })

    data = CreateQuizAssignmentSchema().load(
        valid_assignment_payload
    )

    assert isinstance(data, dict)
    assert data["student_ids"] == [2, 3]


def test_assignment_trims_text_fields(valid_assignment_payload):
    for field in (
        "quiz_id",
        "audience",
        "available_at",
        "deadline_at",
        "review_at",
    ):
        valid_assignment_payload[field] = (
            f"  {valid_assignment_payload[field]}  "
        )

    data = CreateQuizAssignmentSchema().load(
        valid_assignment_payload
    )

    assert isinstance(data, dict)
    assert data["audience"] == "all"
    assert data["quiz_id"] == "12345678-1234-4234-8234-123456789abc"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("quiz_id", "invalid"),
        ("classroom_id", True),
        ("classroom_id", "1"),
        ("classroom_id", 0),
        ("audience", "everyone"),
        ("time_limit_minutes", True),
        ("time_limit_minutes", "30"),
        ("time_limit_minutes", 0),
        ("time_limit_minutes", 181),
        ("max_attempts", True),
        ("max_attempts", "2"),
        ("max_attempts", 0),
        ("max_attempts", 6),
        ("student_ids", [True]),
        ("student_ids", ["2"]),
        ("student_ids", [0]),
        ("student_ids", None),
    ],
)
def test_assignment_rejects_invalid_field_values(
    valid_assignment_payload,
    field,
    value,
):
    valid_assignment_payload[field] = value

    with pytest.raises(ValidationError) as error:
        CreateQuizAssignmentSchema().load(
            valid_assignment_payload
        )

    assert field in error.value.messages


@pytest.mark.parametrize(
    "field",
    ["available_at", "deadline_at", "review_at"],
)
def test_assignment_requires_timezone(
    valid_assignment_payload,
    field,
):
    valid_assignment_payload[field] = "2026-10-06T10:00:00"

    with pytest.raises(ValidationError) as error:
        CreateQuizAssignmentSchema().load(
            valid_assignment_payload
        )

    assert field in error.value.messages


@pytest.mark.parametrize(
    ("audience", "student_ids"),
    [
        ("all", [2]),
        ("selected", []),
        ("selected", [2, 2]),
        ("selected", list(range(1, 502))),
    ],
)
def test_assignment_rejects_invalid_recipient_selection(
    valid_assignment_payload,
    audience,
    student_ids,
):
    valid_assignment_payload.update({
        "audience": audience,
        "student_ids": student_ids,
    })

    with pytest.raises(ValidationError) as error:
        CreateQuizAssignmentSchema().load(
            valid_assignment_payload
        )

    assert "student_ids" in error.value.messages


@pytest.mark.parametrize(
    "deadline",
    [
        "2026-10-06T10:00:00+06:00",
        "2026-10-06T09:59:00+06:00",
    ],
)
def test_assignment_deadline_must_follow_availability(
    valid_assignment_payload,
    deadline,
):
    valid_assignment_payload["deadline_at"] = deadline

    with pytest.raises(ValidationError) as error:
        CreateQuizAssignmentSchema().load(
            valid_assignment_payload
        )

    assert "deadline_at" in error.value.messages


def test_assignment_review_cannot_precede_deadline(
    valid_assignment_payload,
):
    valid_assignment_payload["review_at"] = (
        "2026-10-06T10:59:00+06:00"
    )

    with pytest.raises(ValidationError) as error:
        CreateQuizAssignmentSchema().load(
            valid_assignment_payload
        )

    assert "review_at" in error.value.messages


def test_assignment_compares_different_timezone_offsets(
    valid_assignment_payload,
):
    # 04:00 UTC availability, 05:00 UTC deadline, 06:00 UTC review.
    valid_assignment_payload.update({
        "available_at": "2026-10-06T10:00:00+06:00",
        "deadline_at": "2026-10-06T05:00:00Z",
        "review_at": "2026-10-06T08:00:00+02:00",
    })

    data = CreateQuizAssignmentSchema().load(
        valid_assignment_payload
    )

    assert isinstance(data, dict)
    assert data["available_at"] < data["deadline_at"] < data["review_at"]
    assert data["review_at"].tzinfo == timezone.utc


@pytest.mark.parametrize(
    "field",
    [
        "quiz_id",
        "classroom_id",
        "audience",
        "available_at",
        "deadline_at",
        "time_limit_minutes",
        "review_at",
    ],
)
def test_assignment_requires_mandatory_fields(
    valid_assignment_payload,
    field,
):
    del valid_assignment_payload[field]

    with pytest.raises(ValidationError) as error:
        CreateQuizAssignmentSchema().load(
            valid_assignment_payload
        )

    assert field in error.value.messages


def test_assignment_rejects_teacher_identity_from_request(
    valid_assignment_payload,
):
    valid_assignment_payload["teacher_id"] = 999

    with pytest.raises(ValidationError) as error:
        CreateQuizAssignmentSchema().load(
            valid_assignment_payload
        )

    assert "teacher_id" in error.value.messages


@pytest.mark.parametrize("body", [None, [], "text"])
def test_assignment_rejects_non_object_body(body):
    with pytest.raises(ValidationError):
        CreateQuizAssignmentSchema().load(body)