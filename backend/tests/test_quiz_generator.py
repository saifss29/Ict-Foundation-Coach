import json
from unittest.mock import Mock

import pytest
import requests

from services.quiz_generator import (
    QuizGenerationError,
    generate_quiz,
    parse_generated_questions,
    shuffle_question_options,
)


@pytest.fixture()
def valid_payload():
    return {
        "questions": [
            {
                "question_text": f"Number Systems question {index}",
                "option_a": "2",
                "option_b": "8",
                "option_c": "10",
                "option_d": "16",
                "correct_option": "A",
                "explanation": "Binary uses base 2.",
            }
            for index in range(1, 6)
        ]
    }


@pytest.fixture()
def maira_settings(monkeypatch):
    settings = {
        "MAIRA_API_KEY": "test-api-key",
        "MAIRA_PROJECT_KEY": "test-project-key",
        "MAIRA_ASK_URL": "https://example.com/ask",
        "MAIRA_GPT_PROFILE_ID": "test-profile",
        "MAIRA_SSC_ICT_PROFILE_ID": "test-ssc-ict-profile",
        "MAIRA_HSC_MATH_PROFILE_ID": "test-hsc-math-profile",
        "MAIRA_SSC_MATH_PROFILE_ID": "test-ssc-math-profile",
        "MAIRA_HSC_ENGLISH_PROFILE_ID": "test-hsc-english-profile",
        "MAIRA_SSC_ENGLISH_PROFILE_ID": "test-ssc-english-profile",
        "MAIRA_MEMBER_ID": "test-member",
        "MAIRA_USER_ID": "test-user",
        "MAIRA_USER_NAME": "Test Student",
    }

    for name, value in settings.items():
        monkeypatch.setenv(name, value)


def test_parser_accepts_valid_quiz(valid_payload):
    questions = parse_generated_questions(json.dumps(valid_payload))

    assert len(questions) == 5
    assert [question["id"] for question in questions] == [
        "1", "2", "3", "4", "5"
    ]
    assert questions[0]["correct_option"] == "A"


def test_parser_accepts_json_code_block(valid_payload):
    answer = f"```json\n{json.dumps(valid_payload)}\n```"

    questions = parse_generated_questions(answer)

    assert len(questions) == 5


def test_parser_rejects_non_json_answer():
    with pytest.raises(QuizGenerationError):
        parse_generated_questions("I cannot generate this quiz.")


def test_parser_rejects_wrong_question_count(valid_payload):
    valid_payload["questions"].pop()

    with pytest.raises(QuizGenerationError):
        parse_generated_questions(json.dumps(valid_payload))


def test_parser_rejects_invalid_answer_key(valid_payload):
    valid_payload["questions"][0]["correct_option"] = "E"

    with pytest.raises(QuizGenerationError):
        parse_generated_questions(json.dumps(valid_payload))


def test_parser_rejects_duplicate_options(valid_payload):
    valid_payload["questions"][0]["option_b"] = " 2 "

    with pytest.raises(QuizGenerationError):
        parse_generated_questions(json.dumps(valid_payload))


def test_parser_rejects_duplicate_questions(valid_payload):
    valid_payload["questions"][1]["question_text"] = (
        valid_payload["questions"][0]["question_text"]
    )

    with pytest.raises(QuizGenerationError):
        parse_generated_questions(json.dumps(valid_payload))


def test_parser_rejects_missing_field(valid_payload):
    del valid_payload["questions"][0]["explanation"]

    with pytest.raises(QuizGenerationError):
        parse_generated_questions(json.dumps(valid_payload))


def test_parser_rejects_oversized_option(valid_payload):
    valid_payload["questions"][0]["option_a"] = "A" * 256

    with pytest.raises(QuizGenerationError):
        parse_generated_questions(json.dumps(valid_payload))


def test_generator_returns_validated_quiz(
    monkeypatch,
    maira_settings,
    valid_payload,
):
    response = Mock()
    response.json.return_value = {
        "detail": {
            "response": json.dumps(valid_payload),
        }
    }

    post = Mock(return_value=response)
    monkeypatch.setattr("services.quiz_generator.requests.post", post)

    questions = generate_quiz("Number Systems", "english")

    assert len(questions) == 5
    response.raise_for_status.assert_called_once()

    args, kwargs = post.call_args

    assert args == ("https://example.com/ask",)
    assert kwargs["timeout"] == 60
    assert kwargs["headers"]["api-key"] == "test-api-key"
    assert kwargs["json"]["gpt_profile_id"] == "test-profile"
    assert "Number Systems" in kwargs["json"]["query"]
    assert "clear, simple English" in kwargs["json"]["query"]


def test_generator_rejects_invalid_language(monkeypatch):
    post = Mock()
    monkeypatch.setattr("services.quiz_generator.requests.post", post)

    with pytest.raises(QuizGenerationError) as error:
        generate_quiz("Number Systems", "french")

    assert error.value.status_code == 400
    post.assert_not_called()


def test_generator_rejects_missing_configuration(
    monkeypatch,
    maira_settings,
):
    monkeypatch.delenv("MAIRA_API_KEY")

    post = Mock()
    monkeypatch.setattr("services.quiz_generator.requests.post", post)

    with pytest.raises(QuizGenerationError) as error:
        generate_quiz("Number Systems", "english")

    assert error.value.status_code == 500
    post.assert_not_called()


def test_generator_handles_timeout(monkeypatch, maira_settings):
    post = Mock(side_effect=requests.Timeout())
    monkeypatch.setattr("services.quiz_generator.requests.post", post)

    with pytest.raises(QuizGenerationError) as error:
        generate_quiz("Number Systems", "english")

    assert error.value.status_code == 504


def test_generator_handles_http_failure(monkeypatch, maira_settings):
    response = Mock()
    response.raise_for_status.side_effect = requests.HTTPError()

    monkeypatch.setattr(
        "services.quiz_generator.requests.post",
        Mock(return_value=response),
    )

    with pytest.raises(QuizGenerationError) as error:
        generate_quiz("Number Systems", "english")

    assert error.value.status_code == 502


def test_generator_handles_invalid_response_json(
    monkeypatch,
    maira_settings,
):
    response = Mock()
    response.json.side_effect = ValueError("Invalid JSON")

    monkeypatch.setattr(
        "services.quiz_generator.requests.post",
        Mock(return_value=response),
    )

    with pytest.raises(QuizGenerationError) as error:
        generate_quiz("Number Systems", "english")

    assert error.value.status_code == 502


def test_generator_rejects_empty_answer(monkeypatch, maira_settings):
    response = Mock()
    response.json.return_value = {"detail": {"response": ""}}

    monkeypatch.setattr(
        "services.quiz_generator.requests.post",
        Mock(return_value=response),
    )

    with pytest.raises(QuizGenerationError) as error:
        generate_quiz("Number Systems", "english")

    assert error.value.status_code == 502


def make_count_payload(question_count):
    return {
        "questions": [
            {
                "question_text": f"Number Systems question {index}",
                "option_a": "2",
                "option_b": "8",
                "option_c": "10",
                "option_d": "16",
                "correct_option": "A",
                "explanation": "Binary uses base 2.",
            }
            for index in range(1, question_count + 1)
        ]
    }


@pytest.mark.parametrize("question_count", [1, 5, 10, 20])
def test_parser_accepts_requested_question_count(question_count):
    payload = make_count_payload(question_count)

    questions = parse_generated_questions(
        json.dumps(payload),
        question_count=question_count,
    )

    assert len(questions) == question_count
    assert [question["id"] for question in questions] == [
        str(index)
        for index in range(1, question_count + 1)
    ]


@pytest.mark.parametrize(
    ("requested_count", "returned_count"),
    [(1, 2), (10, 5), (10, 11), (20, 19)],
)
def test_parser_rejects_count_different_from_requested(
    requested_count,
    returned_count,
):
    payload = make_count_payload(returned_count)

    with pytest.raises(QuizGenerationError) as error:
        parse_generated_questions(
            json.dumps(payload),
            question_count=requested_count,
        )

    assert error.value.status_code == 502


@pytest.mark.parametrize(
    "question_count",
    [True, False, "10", 10.0, None, 0, -1, 21],
)
def test_parser_rejects_invalid_requested_count(
    valid_payload,
    question_count,
):
    with pytest.raises(QuizGenerationError) as error:
        parse_generated_questions(
            json.dumps(valid_payload),
            question_count=question_count,
        )

    assert error.value.status_code == 400


@pytest.mark.parametrize("question_count", [1, 10, 20])
def test_generator_uses_requested_count_in_prompt_and_parser(
    monkeypatch,
    maira_settings,
    question_count,
):
    response = Mock()
    response.json.return_value = {
        "detail": {
            "response": json.dumps(
                make_count_payload(question_count)
            ),
        }
    }

    post = Mock(return_value=response)
    monkeypatch.setattr(
        "services.quiz_generator.requests.post",
        post,
    )

    questions = generate_quiz(
        "Number Systems",
        "english",
        question_count=question_count,
    )

    assert len(questions) == question_count
    assert questions[-1]["id"] == str(question_count)
    post.assert_called_once()
    response.raise_for_status.assert_called_once()

    query = post.call_args.kwargs["json"]["query"]

    assert (
        f"Create exactly {question_count} multiple-choice questions"
        in query
    )
    assert (
        f"The questions array must contain exactly {question_count} items."
        in query
    )


def test_generator_rejects_maira_returning_wrong_count(
    monkeypatch,
    maira_settings,
    valid_payload,
):
    response = Mock()
    response.json.return_value = {
        "detail": {
            "response": json.dumps(valid_payload),
        }
    }

    post = Mock(return_value=response)
    monkeypatch.setattr(
        "services.quiz_generator.requests.post",
        post,
    )

    with pytest.raises(QuizGenerationError) as error:
        generate_quiz(
            "Number Systems",
            "english",
            question_count=10,
        )

    assert error.value.status_code == 502
    post.assert_called_once()


@pytest.mark.parametrize(
    "question_count",
    [True, False, "10", 10.0, None, 0, -1, 21],
)
def test_generator_rejects_invalid_count_before_maira_call(
    monkeypatch,
    maira_settings,
    question_count,
):
    post = Mock()
    monkeypatch.setattr(
        "services.quiz_generator.requests.post",
        post,
    )

    with pytest.raises(QuizGenerationError) as error:
        generate_quiz(
            "Number Systems",
            "english",
            question_count=question_count,
        )

    assert error.value.status_code == 400
    post.assert_not_called()


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("learning_mode", "exam"),
        ("learning_mode", ""),
        ("learning_mode", None),
        ("learning_mode", True),
        ("learning_mode", []),
        ("learning_mode", {}),
        ("subject", "physics"),
        ("subject", ""),
        ("subject", None),
        ("subject", True),
        ("subject", []),
        ("subject", {}),
        ("academic_level", "university"),
        ("academic_level", ""),
        ("academic_level", None),
        ("academic_level", True),
        ("academic_level", []),
        ("academic_level", {}),
    ],
)
def test_generator_rejects_invalid_learning_context_before_maira_call(
    monkeypatch,
    maira_settings,
    field,
    invalid_value,
):
    post = Mock()
    monkeypatch.setattr(
        "services.quiz_generator.requests.post",
        post,
    )

    context = {
        "learning_mode": "personal_growth",
        "subject": "ict",
        "academic_level": "hsc",
    }
    context[field] = invalid_value

    with pytest.raises(QuizGenerationError) as error:
        generate_quiz(
            "Number Systems",
            "english",
            learning_mode=context["learning_mode"],
            subject=context["subject"],
            academic_level=context["academic_level"],
        )

    assert error.value.status_code == 400
    post.assert_not_called()


@pytest.mark.parametrize(
    ("learning_mode", "expected_purpose", "excluded_purpose"),
    [
        (
            "personal_growth",
            "Purpose: Personal growth.",
            "Purpose: Exam preparation.",
        ),
        (
            "exam_preparation",
            "Purpose: Exam preparation.",
            "Purpose: Personal growth.",
        ),
    ],
)
@pytest.mark.parametrize(
    ("subject", "subject_label"),
    [
        ("ict", "ICT"),
        ("math", "Mathematics"),
        ("english", "English"),
    ],
)
@pytest.mark.parametrize(
    ("academic_level", "level_label"),
    [
        ("ssc", "SSC (Class 9–10)"),
        ("hsc", "HSC (Class 11–12)"),
    ],
)
def test_generator_sends_selected_learning_context_to_maira(
    monkeypatch,
    maira_settings,
    valid_payload,
    learning_mode,
    expected_purpose,
    excluded_purpose,
    subject,
    subject_label,
    academic_level,
    level_label,
):
    response = Mock()
    response.json.return_value = {
        "detail": {
            "response": json.dumps(valid_payload),
        }
    }

    post = Mock(return_value=response)
    monkeypatch.setattr(
        "services.quiz_generator.requests.post",
        post,
    )

    questions = generate_quiz(
        "Selected Topic",
        "english",
        learning_mode=learning_mode,
        subject=subject,
        academic_level=academic_level,
    )

    assert len(questions) == 5
    post.assert_called_once()

    expected_profiles = {
        ("hsc", "ict"): "test-profile",
        ("ssc", "ict"): "test-ssc-ict-profile",
        ("hsc", "math"): "test-hsc-math-profile",
        ("ssc", "math"): "test-ssc-math-profile",
        ("hsc", "english"): "test-hsc-english-profile",
        ("ssc", "english"): "test-ssc-english-profile",
    }

    assert post.call_args.kwargs["json"]["gpt_profile_id"] == (
        expected_profiles[(academic_level, subject)]
    )

    query = post.call_args.kwargs["json"]["query"]

    assert f"Subject: {subject_label}" in query
    assert f"Academic level: {level_label}" in query
    assert "Topic: Selected Topic" in query
    assert expected_purpose in query
    assert excluded_purpose not in query
    assert "Use only facts supported by the retrieved Reference Context." in query

    if learning_mode == "exam_preparation":
        assert "Do not claim these are official board questions" in query
        assert "Do not invent syllabus requirements or marks distribution." in query
    else:
        assert "Build conceptual understanding and useful skills." in query
        assert "board-style creative question format is not required." in query


def test_generator_defaults_to_personal_growth_hsc_ict(
    monkeypatch,
    maira_settings,
    valid_payload,
):
    response = Mock()
    response.json.return_value = {
        "detail": {
            "response": json.dumps(valid_payload),
        }
    }

    post = Mock(return_value=response)
    monkeypatch.setattr(
        "services.quiz_generator.requests.post",
        post,
    )

    # Existing positional calls must remain compatible.
    questions = generate_quiz("Number Systems", "english", 5)

    assert len(questions) == 5
    post.assert_called_once()

    query = post.call_args.kwargs["json"]["query"]

    assert "Subject: ICT" in query
    assert "Academic level: HSC (Class 11–12)" in query
    assert "Purpose: Personal growth." in query
    assert "Purpose: Exam preparation." not in query


def test_generator_preserves_english_exercises_in_banglish_mode(
    monkeypatch,
    maira_settings,
    valid_payload,
):
    response = Mock()
    response.json.return_value = {
        "detail": {
            "response": json.dumps(valid_payload),
        }
    }

    post = Mock(return_value=response)
    monkeypatch.setattr(
        "services.quiz_generator.requests.post",
        post,
    )

    generate_quiz(
        "Grammar",
        "banglish",
        subject="english",
        academic_level="hsc",
        learning_mode="personal_growth",
    )

    query = post.call_args.kwargs["json"]["query"]

    assert "Bangla written using English letters." in query
    assert "preserve the English sentences or words being tested." in query


@pytest.mark.parametrize("correct_option", ["A", "B", "C", "D"])
def test_shuffle_preserves_correct_answer_and_question_data(
    monkeypatch,
    valid_payload,
    correct_option,
):
    for question in valid_payload["questions"]:
        question["correct_option"] = correct_option

    questions = parse_generated_questions(json.dumps(valid_payload))
    originals = [question.copy() for question in questions]

    # Force a known permutation so this test cannot randomly pass.
    randomizer = Mock()
    randomizer.shuffle.side_effect = lambda options: options.reverse()

    monkeypatch.setattr(
        "services.quiz_generator.SystemRandom",
        Mock(return_value=randomizer),
    )

    shuffled = shuffle_question_options(questions)

    expected_labels = {
        "A": "D",
        "B": "C",
        "C": "B",
        "D": "A",
    }

    assert questions == originals
    assert randomizer.shuffle.call_count == len(questions)

    for original, result in zip(originals, shuffled):
        assert result["correct_option"] == expected_labels[correct_option]

        correct_text = original[f"option_{correct_option.lower()}"]
        new_correct_field = f"option_{result['correct_option'].lower()}"

        assert result[new_correct_field] == correct_text

        assert [
            result[f"option_{label}"]
            for label in ("a", "b", "c", "d")
        ] == [
            original[f"option_{label}"]
            for label in ("d", "c", "b", "a")
        ]

        for field in ("id", "question_text", "explanation"):
            assert result[field] == original[field]

        assert set(result) == set(original)


def test_generator_returns_shuffled_options_with_correct_mapping(
    monkeypatch,
    maira_settings,
    valid_payload,
):
    response = Mock()
    response.json.return_value = {
        "detail": {
            "response": json.dumps(valid_payload),
        }
    }

    monkeypatch.setattr(
        "services.quiz_generator.requests.post",
        Mock(return_value=response),
    )

    randomizer = Mock()
    randomizer.shuffle.side_effect = lambda options: options.reverse()

    monkeypatch.setattr(
        "services.quiz_generator.SystemRandom",
        Mock(return_value=randomizer),
    )

    questions = generate_quiz("Number Systems", "english")

    assert len(questions) == 5
    assert randomizer.shuffle.call_count == 5

    for question in questions:
        assert question["option_a"] == "16"
        assert question["option_b"] == "10"
        assert question["option_c"] == "8"
        assert question["option_d"] == "2"
        assert question["correct_option"] == "D"
        assert question["explanation"] == "Binary uses base 2."


def make_maira_response(payload):
    response = Mock()
    response.json.return_value = {
        "detail": {"response": json.dumps(payload)}
    }
    return response


def test_missing_answer_key_retries_once_and_returns_valid_quiz(
    monkeypatch, maira_settings, valid_payload
):
    incomplete = json.loads(json.dumps(valid_payload))
    del incomplete["questions"][0]["correct_option"]

    post = Mock(side_effect=[
        make_maira_response(incomplete),
        make_maira_response(valid_payload),
    ])
    monkeypatch.setattr("services.quiz_generator.requests.post", post)

    questions = generate_quiz("Number Systems", "english")

    assert post.call_count == 2
    assert len(questions) == 5

    for question in questions:
        correct_field = f"option_{question['correct_option'].lower()}"
        assert question[correct_field] == "2"

    first = post.call_args_list[0].kwargs["json"]
    second = post.call_args_list[1].kwargs["json"]

    assert first["session_id"] != second["session_id"]
    assert first["gpt_profile_id"] == second["gpt_profile_id"]
    assert second["query"].startswith(first["query"])


def test_second_missing_answer_key_is_rejected_without_third_call(
    monkeypatch, maira_settings, valid_payload
):
    del valid_payload["questions"][0]["correct_option"]

    post = Mock(side_effect=[
        make_maira_response(valid_payload),
        make_maira_response(valid_payload),
    ])
    monkeypatch.setattr("services.quiz_generator.requests.post", post)

    with pytest.raises(QuizGenerationError):
        generate_quiz("Number Systems", "english")

    assert post.call_count == 2


def test_other_missing_field_does_not_trigger_retry(
    monkeypatch, maira_settings, valid_payload
):
    del valid_payload["questions"][0]["explanation"]

    post = Mock(return_value=make_maira_response(valid_payload))
    monkeypatch.setattr("services.quiz_generator.requests.post", post)

    with pytest.raises(QuizGenerationError):
        generate_quiz("Number Systems", "english")

    post.assert_called_once()


def test_missing_answer_key_in_code_block_retries_once(
    monkeypatch, maira_settings, valid_payload
):
    incomplete = json.loads(json.dumps(valid_payload))
    del incomplete["questions"][0]["correct_option"]

    first_response = Mock()
    first_response.json.return_value = {
        "detail": {
            "response": f"```json\n{json.dumps(incomplete)}\n```",
        }
    }

    post = Mock(side_effect=[
        first_response,
        make_maira_response(valid_payload),
    ])
    monkeypatch.setattr("services.quiz_generator.requests.post", post)

    questions = generate_quiz("Number Systems", "english")

    assert post.call_count == 2
    assert len(questions) == 5

    for question in questions:
        correct_field = f"option_{question['correct_option'].lower()}"
        assert question[correct_field] == "2"