import pytest
from marshmallow import ValidationError

from schemas.teacher_quiz_schema import (
    CreateTeacherQuizSchema,
    UpdateTeacherQuizSchema,
)


def make_questions(count: int) -> list[dict[str, str]]:
    return [
        {
            "id": str(index),
            "question_text": f"Practice question {index}",
            "option_a": "2",
            "option_b": "8",
            "option_c": "10",
            "option_d": "16",
            "correct_option": "A",
            "explanation": "Binary uses base 2.",
        }
        for index in range(1, count + 1)
    ]


def test_create_defaults_to_five_questions():
    data = CreateTeacherQuizSchema().load({
        "topic_id": 1,
        "title": "Practice Quiz",
    })

    assert isinstance(data, dict)
    assert data["question_count"] == 5


@pytest.mark.parametrize("count", [1, 5, 10, 20])
def test_create_accepts_selected_count(count):
    data = CreateTeacherQuizSchema().load({
        "topic_id": 1,
        "title": "Practice Quiz",
        "question_count": count,
    })

    assert isinstance(data, dict)
    assert data["question_count"] == count


@pytest.mark.parametrize(
    "count",
    [True, False, "10", 10.0, None, 0, -1, 21],
)
def test_create_rejects_invalid_count(count):
    with pytest.raises(ValidationError) as error:
        CreateTeacherQuizSchema().load({
            "topic_id": 1,
            "title": "Practice Quiz",
            "question_count": count,
        })

    assert "question_count" in error.value.messages


@pytest.mark.parametrize("count", [1, 5, 10, 20])
def test_update_accepts_expected_count(count):
    data = UpdateTeacherQuizSchema(
        expected_question_count=count,
    ).load({
        "title": "Updated Practice Quiz",
        "questions": make_questions(count),
    })

    assert isinstance(data, dict)
    assert len(data["questions"]) == count


@pytest.mark.parametrize("count", [4, 6])
def test_update_default_still_requires_five(count):
    with pytest.raises(ValidationError):
        UpdateTeacherQuizSchema().load({
            "title": "Updated Practice Quiz",
            "questions": make_questions(count),
        })


@pytest.mark.parametrize("returned_count", [9, 11])
def test_update_rejects_count_different_from_expected(returned_count):
    with pytest.raises(ValidationError) as error:
        UpdateTeacherQuizSchema(
            expected_question_count=10,
        ).load({
            "title": "Updated Practice Quiz",
            "questions": make_questions(returned_count),
        })

    assert "questions" in error.value.messages


@pytest.mark.parametrize(
    ("index", "replacement_id"),
    [
        (9, "9"),
        (9, "11"),
        (9, "21"),
        (9, 10),
    ],
)
def test_update_rejects_invalid_ids_for_ten_questions(
    index,
    replacement_id,
):
    questions = make_questions(10)

    # Build an invalid request without changing the helper's string types.
    invalid_questions = [
        {
            **question,
            "id": (
                replacement_id
                if position == index
                else question["id"]
            ),
        }
        for position, question in enumerate(questions)
    ]

    with pytest.raises(ValidationError):
        UpdateTeacherQuizSchema(
            expected_question_count=10,
        ).load({
            "title": "Updated Practice Quiz",
            "questions": invalid_questions,
        })


def test_update_rejects_duplicate_questions_with_selected_count():
    questions = make_questions(10)
    questions[9]["question_text"] = (
        "  " + questions[0]["question_text"].upper() + "  "
    )

    with pytest.raises(ValidationError) as error:
        UpdateTeacherQuizSchema(
            expected_question_count=10,
        ).load({
            "title": "Updated Practice Quiz",
            "questions": questions,
        })

    assert "questions" in error.value.messages


def test_update_rejects_client_supplied_expected_count():
    with pytest.raises(ValidationError) as error:
        UpdateTeacherQuizSchema().load({
            "title": "Updated Practice Quiz",
            "questions": make_questions(5),
            "expected_question_count": 10,
        })

    assert "expected_question_count" in error.value.messages


@pytest.mark.parametrize(
    "count",
    [True, False, "10", 10.0, None, 0, -1, 21],
)
def test_update_constructor_rejects_invalid_expected_count(count):
    with pytest.raises(ValueError):
        UpdateTeacherQuizSchema(
            expected_question_count=count,
        )