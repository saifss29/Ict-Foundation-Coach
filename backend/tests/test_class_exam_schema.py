from decimal import Decimal

import pytest
from marshmallow import ValidationError

from schemas.class_exam_schema import (
    CreateClassExamSchema,
    UpdateClassExamResultsSchema,
)


def exam_payload():
    return {
        "title": "1st Term ICT",
        "total_marks": 30,
        "starts_at": "2026-11-01T10:00:00+06:00",
        "ends_at": "2026-11-01T11:00:00+06:00",
        "timezone_name": "Asia/Dhaka",
    }


def test_valid_exam_normalizes_text_and_loads_marks():
    payload = exam_payload()
    payload["title"] = "  1st Term ICT  "
    payload["description"] = "  Bring a pen.  "

    data = CreateClassExamSchema().load(payload)
    assert isinstance(data, dict)

    assert data["title"] == "1st Term ICT"
    assert data["description"] == "Bring a pen."
    assert data["total_marks"] == Decimal("30")
    assert data["starts_at"].utcoffset() is not None


def test_exam_description_defaults_to_empty():
    data = CreateClassExamSchema().load(exam_payload())
    assert isinstance(data, dict)
    assert data["description"] == ""


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", "  "),
        ("title", "x" * 151),
        ("description", "x" * 2001),
        ("total_marks", 0),
        ("total_marks", -1),
        ("total_marks", True),
        ("total_marks", None),
        ("total_marks", "NaN"),
        ("total_marks", "Infinity"),
        ("total_marks", "30.001"),
        ("total_marks", "10000"),
        ("starts_at", "2026-11-01T10:00:00"),
        ("ends_at", "2026-11-01T10:00:00+06:00"),
        ("ends_at", "2026-11-01T09:00:00+06:00"),
        ("timezone_name", "Not/AZone"),
        ("timezone_name", ""),
    ],
)
def test_invalid_exam_field_is_rejected(field, value):
    payload = exam_payload()
    payload[field] = value

    with pytest.raises(ValidationError) as error:
        CreateClassExamSchema().load(payload)

    assert field in error.value.messages


def test_exam_rejects_client_owned_fields():
    payload = exam_payload()
    payload["teacher_id"] = 123

    with pytest.raises(ValidationError) as error:
        CreateClassExamSchema().load(payload)

    assert "teacher_id" in error.value.messages


@pytest.mark.parametrize("body", [None, [], "exam"])
def test_exam_requires_object(body):
    with pytest.raises(ValidationError):
        CreateClassExamSchema().load(body)


def test_marks_and_absent_entries_load():
    data = UpdateClassExamResultsSchema().load({
        "results": [
            {
                "student_id": 1,
                "obtained_marks": "22.50",
            },
            {
                "student_id": 2,
                "is_absent": True,
            },
            {
                "student_id": 3,
                "obtained_marks": 0,
            },
        ]
    })

    assert isinstance(data, dict)
    assert data["results"][0]["obtained_marks"] == Decimal("22.50")
    assert data["results"][0]["is_absent"] is False
    assert data["results"][1]["obtained_marks"] is None
    assert data["results"][1]["is_absent"] is True
    assert data["results"][2]["obtained_marks"] == Decimal("0")


@pytest.mark.parametrize(
    "entry",
    [
        {"student_id": 0, "obtained_marks": 10},
        {"student_id": True, "obtained_marks": 10},
        {"student_id": 1.5, "obtained_marks": 10},
        {"student_id": 1, "obtained_marks": -1},
        {"student_id": 1, "obtained_marks": True},
        {"student_id": 1, "obtained_marks": "1.001"},
        {"student_id": 1, "obtained_marks": "NaN"},
        {"student_id": 1},
        {
            "student_id": 1,
            "obtained_marks": 10,
            "is_absent": True,
        },
        {
            "student_id": 1,
            "obtained_marks": 10,
            "is_absent": "false",
        },
        {
            "student_id": 1,
            "obtained_marks": 10,
            "unexpected": "value",
        },
    ],
)
def test_invalid_result_entry_is_rejected(entry):
    with pytest.raises(ValidationError):
        UpdateClassExamResultsSchema().load({
            "results": [entry]
        })


def test_duplicate_students_are_rejected():
    with pytest.raises(ValidationError) as error:
        UpdateClassExamResultsSchema().load({
            "results": [
                {"student_id": 1, "obtained_marks": 10},
                {"student_id": 1, "obtained_marks": 20},
            ]
        })

    assert "results" in error.value.messages


@pytest.mark.parametrize("results", [[], None, "marks"])
def test_results_require_nonempty_list(results):
    with pytest.raises(ValidationError):
        UpdateClassExamResultsSchema().load({
            "results": results
        })


@pytest.mark.parametrize("body", [None, [], "results"])
def test_results_require_object(body):
    with pytest.raises(ValidationError):
        UpdateClassExamResultsSchema().load(body)


def test_results_reject_unknown_top_level_fields():
    with pytest.raises(ValidationError) as error:
        UpdateClassExamResultsSchema().load({
            "results": [
                {"student_id": 1, "obtained_marks": 10}
            ],
            "results_published_at": "2026-11-01",
        })

    assert "results_published_at" in error.value.messages