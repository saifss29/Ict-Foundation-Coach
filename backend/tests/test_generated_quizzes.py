from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

import pytest

from extensions import db
from models.generated_quiz import GeneratedQuiz
from models.quiz_attempt import QuizAttempt
from models.topic import Topic
from services.quiz_generator import QuizGenerationError
from models.user import User
from models.chat_conversation import ChatConversation
from models.chat_message import ChatMessage


def login_as(client, *, email, role="student", academic_level="hsc"):
    registration_data = {
        "name": f"Test {role.title()}",
        "email": email,
        "password": "SecurePass123!",
        "role": role,
    }

    if role == "student":
        registration_data["academic_level"] = academic_level

    with patch(
        "services.email_verification_service.send_email"
    ) as mock_send_email:
        register_response = client.post(
            "/api/auth/register",
            json=registration_data,
        )

        assert register_response.status_code == 201
        mock_send_email.assert_called_once()

        email_body = mock_send_email.call_args.kwargs["body"]

    verification_link = next(
        line.strip()
        for line in email_body.splitlines()
        if line.strip().startswith(
            "http://localhost:5173/verify-email?"
        )
    )

    verification_token = parse_qs(
        urlsplit(verification_link).query
    )["token"][0]

    verification_response = client.post(
        "/api/auth/verify-email",
        json={"token": verification_token},
    )

    assert verification_response.status_code == 200

    login_response = client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": "SecurePass123!",
        },
    )

    assert login_response.status_code == 200

    token = login_response.get_json()["access_token"]

    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def student_headers(client):
    return login_as(
        client,
        email="student@example.com",
    )


@pytest.fixture()
def number_systems_topic(app):
    with app.app_context():
        topic = Topic(
            title="Number Systems",
            slug="number-systems",
            description="Number Systems test content.",
            display_order=1,
        )

        db.session.add(topic)
        db.session.commit()

        return topic.id


@pytest.fixture(autouse=True)
def mock_generator(monkeypatch):
    questions = [
        {
            "id": str(index),
            "question_text": f"Test question {index}",
            "option_a": "Option A",
            "option_b": "Option B",
            "option_c": "Option C",
            "option_d": "Option D",
            "correct_option": correct_option,
            "explanation": f"Explanation {index}",
        }
        for index, correct_option in enumerate(
            ["A", "B", "C", "D", "A"],
            start=1,
        )
    ]

    generator = Mock(return_value=questions)

    # Patch where the route uses the function.
    monkeypatch.setattr(
        "routes.generated_quizzes.generate_quiz",
        generator,
    )

    return generator


def create_quiz(client, headers):
    response = client.post(
        "/api/generated-quizzes",
        headers=headers,
        json={
            "topic_slug": "number-systems",
            "response_language": "english",
        },
    )

    assert response.status_code == 201

    return response.get_json()["quiz"]


def answer_payload(options=None):
    if options is None:
        options = ["A", "B", "C", "D", "A"]

    return {
        "answers": [
            {
                "question_id": index,
                "selected_option": option,
            }
            for index, option in enumerate(options, start=1)
        ]
    }


def assert_answers_are_hidden(quiz):
    for question in quiz["questions"]:
        assert set(question) == {
            "id",
            "question_text",
            "options",
        }

        assert "correct_option" not in question
        assert "explanation" not in question
        assert len(question["options"]) == 4


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/generated-quizzes"),
        ("GET", "/api/generated-quizzes/unknown"),
        ("POST", "/api/generated-quizzes/unknown/submit"),
    ],
)
def test_generated_quiz_routes_require_login(client, method, path):
    response = client.open(path, method=method)

    assert response.status_code == 401


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/generated-quizzes"),
        ("GET", "/api/generated-quizzes/unknown"),
        ("POST", "/api/generated-quizzes/unknown/submit"),
    ],
)
def test_teacher_cannot_use_generated_quiz_routes(client, method, path):
    headers = login_as(
        client,
        email="teacher@example.com",
        role="teacher",
    )

    response = client.open(
        path,
        method=method,
        headers=headers,
    )

    assert response.status_code == 403


def test_student_can_generate_quiz_without_answer_leak(
    app,
    client,
    student_headers,
    number_systems_topic,
    mock_generator,
):
    quiz = create_quiz(client, student_headers)

    assert quiz["topic"]["slug"] == "number-systems"
    assert quiz["response_language"] == "english"
    assert len(quiz["questions"]) == 5

    assert_answers_are_hidden(quiz)

    assert quiz["learning_mode"] == "personal_growth"
    assert quiz["topic"]["subject"] == "ict"
    assert quiz["topic"]["academic_level"] == "hsc"

    mock_generator.assert_called_once_with(
        topic_title="Number Systems",
        response_language="english",
        learning_mode="personal_growth",
        subject="ict",
        academic_level="hsc",
    )

    with app.app_context():
        saved_quiz = db.session.get(GeneratedQuiz, quiz["id"])

        assert saved_quiz is not None
        assert saved_quiz.topic_id == number_systems_topic
        assert saved_quiz.questions[0]["correct_option"] == "A"
        assert saved_quiz.attempt_id is None


def test_student_can_reload_own_quiz(
    client,
    student_headers,
    number_systems_topic,
):
    quiz = create_quiz(client, student_headers)

    response = client.get(
        f"/api/generated-quizzes/{quiz['id']}",
        headers=student_headers,
    )

    assert response.status_code == 200

    loaded_quiz = response.get_json()["quiz"]

    assert loaded_quiz["id"] == quiz["id"]
    assert_answers_are_hidden(loaded_quiz)


@pytest.mark.parametrize("action", ["load", "submit"])
def test_student_cannot_access_another_students_quiz(
    client,
    student_headers,
    number_systems_topic,
    action,
):
    quiz = create_quiz(client, student_headers)

    other_headers = login_as(
        client,
        email="other-student@example.com",
    )

    if action == "load":
        response = client.get(
            f"/api/generated-quizzes/{quiz['id']}",
            headers=other_headers,
        )
    else:
        response = client.post(
            f"/api/generated-quizzes/{quiz['id']}/submit",
            headers=other_headers,
            json=answer_payload(),
        )

    assert response.status_code == 404


@pytest.mark.parametrize("action", ["load", "submit"])
def test_expired_quiz_cannot_be_used(
    app,
    client,
    student_headers,
    number_systems_topic,
    action,
):
    quiz = create_quiz(client, student_headers)

    with app.app_context():
        saved_quiz = db.session.get(GeneratedQuiz, quiz["id"])

        assert saved_quiz is not None

        saved_quiz.expires_at = (
            datetime.now(timezone.utc) - timedelta(minutes=1)
        )

        db.session.commit()

    if action == "load":
        response = client.get(
            f"/api/generated-quizzes/{quiz['id']}",
            headers=student_headers,
        )
    else:
        response = client.post(
            f"/api/generated-quizzes/{quiz['id']}/submit",
            headers=student_headers,
            json=answer_payload(),
        )

    assert response.status_code == 410

    with app.app_context():
        attempts = db.session.scalars(
            db.select(QuizAttempt)
        ).all()

        assert len(attempts) == 0


def test_submission_scores_and_updates_progress(
    app,
    client,
    student_headers,
    number_systems_topic,
):
    quiz = create_quiz(client, student_headers)

    response = client.post(
        f"/api/generated-quizzes/{quiz['id']}/submit",
        headers=student_headers,
        json=answer_payload(["A", "B", "D", "D", "B"]),
    )

    assert response.status_code == 201

    data = response.get_json()

    assert data["attempt"]["score"] == 3
    assert data["attempt"]["total_questions"] == 5

    assert [
        result["is_correct"]
        for result in data["results"]
    ] == [True, True, False, True, False]

    assert data["results"][0]["correct_option"] == "A"
    assert data["results"][0]["explanation"] == "Explanation 1"

    with app.app_context():
        saved_quiz = db.session.get(GeneratedQuiz, quiz["id"])

        assert saved_quiz is not None
        assert saved_quiz.attempt_id == data["attempt"]["id"]

        attempt = db.session.get(
            QuizAttempt,
            data["attempt"]["id"],
        )

        assert attempt is not None
        assert attempt.topic_id == number_systems_topic
        assert attempt.score == 3

    progress_response = client.get(
        "/api/progress",
        headers=student_headers,
    )

    assert progress_response.status_code == 200

    topic_progress = next(
        topic
        for topic in progress_response.get_json()["topics"]
        if topic["slug"] == "number-systems"
    )

    assert topic_progress["attempt_count"] == 1
    assert topic_progress["percentage"] == 60


def test_submitted_quiz_cannot_be_submitted_or_loaded_again(
    app,
    client,
    student_headers,
    number_systems_topic,
):
    quiz = create_quiz(client, student_headers)
    submit_url = f"/api/generated-quizzes/{quiz['id']}/submit"

    first_response = client.post(
        submit_url,
        headers=student_headers,
        json=answer_payload(),
    )

    second_response = client.post(
        submit_url,
        headers=student_headers,
        json=answer_payload(),
    )

    load_response = client.get(
        f"/api/generated-quizzes/{quiz['id']}",
        headers=student_headers,
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert load_response.status_code == 409

    with app.app_context():
        attempts = db.session.scalars(
            db.select(QuizAttempt)
        ).all()

        assert len(attempts) == 1


@pytest.mark.parametrize(
    "question_ids",
    [
        [1, 2, 3, 4],
        [1, 2, 3, 4, 4],
        [1, 2, 3, 4, 99],
    ],
)
def test_submission_rejects_missing_duplicate_or_foreign_questions(
    app,
    client,
    student_headers,
    number_systems_topic,
    question_ids,
):
    quiz = create_quiz(client, student_headers)

    response = client.post(
        f"/api/generated-quizzes/{quiz['id']}/submit",
        headers=student_headers,
        json={
            "answers": [
                {
                    "question_id": question_id,
                    "selected_option": "A",
                }
                for question_id in question_ids
            ]
        },
    )

    assert response.status_code == 400

    with app.app_context():
        saved_quiz = db.session.get(GeneratedQuiz, quiz["id"])

        assert saved_quiz is not None
        assert saved_quiz.attempt_id is None

        attempts = db.session.scalars(
            db.select(QuizAttempt)
        ).all()

        assert len(attempts) == 0


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"topic_slug": 123},
        {
            "topic_slug": "number-systems",
            "response_language": "french",
        },
        {
            "topic_slug": "number-systems",
            "response_language": None,
        },
        {
            "topic_slug": "number-systems",
            "user_id": 999,
        },
    ],
)
def test_generation_rejects_invalid_input(
    client,
    student_headers,
    number_systems_topic,
    mock_generator,
    payload,
):
    response = client.post(
        "/api/generated-quizzes",
        headers=student_headers,
        json=payload,
    )

    assert response.status_code == 400
    mock_generator.assert_not_called()


def test_generation_rejects_unknown_topic(
    client,
    student_headers,
    mock_generator,
):
    response = client.post(
        "/api/generated-quizzes",
        headers=student_headers,
        json={"topic_slug": "missing-topic"},
    )

    assert response.status_code == 404
    mock_generator.assert_not_called()


def test_generation_rejects_topic_without_rag_support(
    app,
    client,
    student_headers,
    mock_generator,
):
    with app.app_context():
        topic = Topic(
            title="Variables",
            slug="variables",
            description="Variables test content.",
            display_order=1,
        )

        db.session.add(topic)
        db.session.commit()

    response = client.post(
        "/api/generated-quizzes",
        headers=student_headers,
        json={"topic_slug": "variables"},
    )

    assert response.status_code == 400
    mock_generator.assert_not_called()


def test_generation_failure_does_not_save_quiz(
    app,
    client,
    student_headers,
    number_systems_topic,
    mock_generator,
):
    mock_generator.side_effect = QuizGenerationError(
        "Quiz generation timed out.",
        status_code=504,
    )

    response = client.post(
        "/api/generated-quizzes",
        headers=student_headers,
        json={"topic_slug": "number-systems"},
    )

    assert response.status_code == 504

    with app.app_context():
        quizzes = db.session.scalars(
            db.select(GeneratedQuiz)
        ).all()

        assert len(quizzes) == 0

@pytest.mark.parametrize(
    "learning_mode",
    ["personal_growth", "exam_preparation"],
)
def test_generated_quiz_mode_is_saved_and_returned_on_reload(
    app,
    client,
    student_headers,
    number_systems_topic,
    mock_generator,
    learning_mode,
):
    response = client.post(
        "/api/generated-quizzes",
        headers=student_headers,
        json={
            "topic_slug": "number-systems",
            "response_language": "english",
            "learning_mode": learning_mode,
        },
    )

    assert response.status_code == 201

    quiz = response.get_json()["quiz"]

    assert quiz["learning_mode"] == learning_mode
    assert quiz["topic"]["subject"] == "ict"
    assert quiz["topic"]["academic_level"] == "hsc"
    assert_answers_are_hidden(quiz)

    mock_generator.assert_called_once_with(
        topic_title="Number Systems",
        response_language="english",
        learning_mode=learning_mode,
        subject="ict",
        academic_level="hsc",
    )

    with app.app_context():
        saved_quiz = db.session.get(GeneratedQuiz, quiz["id"])

        assert saved_quiz is not None
        assert saved_quiz.learning_mode == learning_mode
        assert saved_quiz.topic_id == number_systems_topic

    loaded_response = client.get(
        f"/api/generated-quizzes/{quiz['id']}",
        headers=student_headers,
    )

    assert loaded_response.status_code == 200

    loaded_quiz = loaded_response.get_json()["quiz"]

    assert loaded_quiz["learning_mode"] == learning_mode
    assert_answers_are_hidden(loaded_quiz)

    # Reload must not generate another quiz.
    mock_generator.assert_called_once()


@pytest.mark.parametrize(
    "learning_mode",
    [
        None,
        "",
        "exam",
        "PERSONAL_GROWTH",
        " personal_growth ",
        True,
        123,
        [],
        {},
    ],
)
def test_generated_quiz_rejects_invalid_mode_without_saving(
    app,
    client,
    student_headers,
    number_systems_topic,
    mock_generator,
    learning_mode,
):
    response = client.post(
        "/api/generated-quizzes",
        headers=student_headers,
        json={
            "topic_slug": "number-systems",
            "learning_mode": learning_mode,
        },
    )

    assert response.status_code == 400
    mock_generator.assert_not_called()

    with app.app_context():
        saved_quiz_id = db.session.scalar(
            db.select(GeneratedQuiz.id)
        )

        assert saved_quiz_id is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("subject", "math"),
        ("academic_level", "ssc"),
    ],
)
def test_generated_quiz_rejects_client_topic_context_override(
    client,
    student_headers,
    number_systems_topic,
    mock_generator,
    field,
    value,
):
    payload = {
        "topic_slug": "number-systems",
        "learning_mode": "personal_growth",
    }
    payload[field] = value

    response = client.post(
        "/api/generated-quizzes",
        headers=student_headers,
        json=payload,
    )

    assert response.status_code == 400
    mock_generator.assert_not_called()

@pytest.mark.parametrize("academic_level", ["ssc", "hsc"])
def test_matching_level_can_generate_reload_and_submit(
    app,
    client,
    number_systems_topic,
    mock_generator,
    academic_level,
):
    # Test-only topic context; this does not enable a real SSC dataset.
    with app.app_context():
        topic = db.session.get(Topic, number_systems_topic)
        assert topic is not None
        topic.academic_level = academic_level
        db.session.commit()

    headers = login_as(
        client,
        email="matching-level@example.com",
        academic_level=academic_level,
    )

    quiz = create_quiz(client, headers)

    assert quiz["topic"]["academic_level"] == academic_level
    assert_answers_are_hidden(quiz)

    mock_generator.assert_called_once_with(
        topic_title="Number Systems",
        response_language="english",
        learning_mode="personal_growth",
        subject="ict",
        academic_level=academic_level,
    )

    loaded_response = client.get(
        f"/api/generated-quizzes/{quiz['id']}",
        headers=headers,
    )

    assert loaded_response.status_code == 200
    assert_answers_are_hidden(loaded_response.get_json()["quiz"])

    submit_response = client.post(
        f"/api/generated-quizzes/{quiz['id']}/submit",
        headers=headers,
        json=answer_payload(),
    )

    assert submit_response.status_code == 201
    assert submit_response.get_json()["attempt"]["score"] == 5

    with app.app_context():
        saved_quiz = db.session.get(GeneratedQuiz, quiz["id"])
        assert saved_quiz is not None
        assert saved_quiz.attempt_id is not None
        assert db.session.get(QuizAttempt, saved_quiz.attempt_id) is not None

    mock_generator.assert_called_once()


@pytest.mark.parametrize(
    ("student_level", "expected_status", "expected_code"),
    [
        ("ssc", 403, "TOPIC_LEVEL_MISMATCH"),
        (None, 409, "ACADEMIC_LEVEL_REQUIRED"),
    ],
)
def test_generation_rejects_unavailable_level_before_generator(
    app,
    client,
    student_headers,
    number_systems_topic,
    mock_generator,
    student_level,
    expected_status,
    expected_code,
):
    with app.app_context():
        user = db.session.scalar(
            db.select(User).where(User.email == "student@example.com")
        )
        assert user is not None
        user.academic_level = student_level
        db.session.commit()

    response = client.post(
        "/api/generated-quizzes",
        headers=student_headers,
        json={"topic_slug": "number-systems"},
    )

    assert response.status_code == expected_status
    assert response.get_json()["code"] == expected_code
    assert "quiz" not in response.get_json()
    mock_generator.assert_not_called()

    with app.app_context():
        assert db.session.scalar(db.select(GeneratedQuiz.id)) is None
        assert db.session.scalar(db.select(QuizAttempt.id)) is None


@pytest.mark.parametrize("action", ["load", "submit"])
@pytest.mark.parametrize(
    ("student_level", "expected_status", "expected_code"),
    [
        ("ssc", 403, "TOPIC_LEVEL_MISMATCH"),
        (None, 409, "ACADEMIC_LEVEL_REQUIRED"),
    ],
)
def test_saved_quiz_rechecks_current_student_level(
    app,
    client,
    student_headers,
    number_systems_topic,
    mock_generator,
    action,
    student_level,
    expected_status,
    expected_code,
):
    quiz = create_quiz(client, student_headers)

    # Simulate an old quiz whose owner's current level no longer matches.
    with app.app_context():
        user = db.session.scalar(
            db.select(User).where(User.email == "student@example.com")
        )
        assert user is not None
        user.academic_level = student_level
        db.session.commit()

    if action == "load":
        response = client.get(
            f"/api/generated-quizzes/{quiz['id']}",
            headers=student_headers,
        )
    else:
        response = client.post(
            f"/api/generated-quizzes/{quiz['id']}/submit",
            headers=student_headers,
            json=answer_payload(),
        )

    assert response.status_code == expected_status

    data = response.get_json()
    assert data["code"] == expected_code
    assert "quiz" not in data
    assert "results" not in data
    assert "attempt" not in data

    with app.app_context():
        saved_quiz = db.session.get(GeneratedQuiz, quiz["id"])
        assert saved_quiz is not None
        assert saved_quiz.attempt_id is None
        assert db.session.scalar(db.select(QuizAttempt.id)) is None

    mock_generator.assert_called_once()


def save_quiz_discussion(
    app,
    *,
    email="student@example.com",
    topic="Number Systems",
    messages=None,
):
    if messages is None:
        messages = [
            ("student", "Binary 101 decimal-e koto?"),
            ("assistant", "Binary 101 equals decimal 5."),
        ]

    with app.app_context():
        user = db.session.scalar(
            db.select(User).where(User.email == email)
        )
        assert user is not None

        conversation = ChatConversation(
            user_id=user.id,
            title="Quiz discussion",
            topic=topic,
            response_language="english",
            learning_mode="exam_preparation",
        )
        db.session.add(conversation)
        db.session.flush()

        for role, content in messages:
            db.session.add(ChatMessage(
                conversation_id=conversation.id,
                role=role,
                content=content,
            ))

        db.session.commit()
        return conversation.id


def test_discussion_quiz_saves_context_and_reloads(
    app,
    client,
    student_headers,
    number_systems_topic,
    mock_generator,
):
    conversation_id = save_quiz_discussion(app)

    response = client.post(
        "/api/generated-quizzes",
        headers=student_headers,
        json={
            "topic_slug": "number-systems",
            "conversation_id": conversation_id,
        },
    )

    assert response.status_code == 201
    quiz = response.get_json()["quiz"]

    assert quiz["response_language"] == "english"
    assert quiz["learning_mode"] == "exam_preparation"
    assert quiz["practice_topic"] == "Binary 101 decimal-e koto?"
    assert_answers_are_hidden(quiz)

    mock_generator.assert_called_once_with(
        topic_title="Binary 101 decimal-e koto?",
        response_language="english",
        learning_mode="exam_preparation",
        subject="ict",
        academic_level="hsc",
        discussion_context=(
            "student: Binary 101 decimal-e koto?\n\n"
            "assistant: Binary 101 equals decimal 5."
        ),
    )

    with app.app_context():
        saved = db.session.get(GeneratedQuiz, quiz["id"])
        assert saved is not None
        assert saved.practice_topic == quiz["practice_topic"]
        assert saved.topic_id == number_systems_topic

    loaded = client.get(
        f"/api/generated-quizzes/{quiz['id']}",
        headers=student_headers,
    )

    assert loaded.status_code == 200
    loaded_quiz = loaded.get_json()["quiz"]
    assert loaded_quiz["practice_topic"] == quiz["practice_topic"]
    assert_answers_are_hidden(loaded_quiz)
    mock_generator.assert_called_once()


def test_discussion_quiz_rejects_another_students_chat(
    app,
    client,
    student_headers,
    number_systems_topic,
    mock_generator,
):
    conversation_id = save_quiz_discussion(app)

    other_headers = login_as(
        client,
        email="other-discussion@example.com",
    )

    response = client.post(
        "/api/generated-quizzes",
        headers=other_headers,
        json={
            "topic_slug": "number-systems",
            "conversation_id": conversation_id,
        },
    )

    assert response.status_code == 404
    mock_generator.assert_not_called()

    with app.app_context():
        assert db.session.scalar(db.select(GeneratedQuiz.id)) is None


@pytest.mark.parametrize(
    "changes",
    [
        {"response_language": "banglish"},
        {"learning_mode": "personal_growth"},
        {"conversation_topic": "Variables"},
    ],
)
def test_discussion_quiz_rejects_context_mismatch(
    app,
    client,
    student_headers,
    number_systems_topic,
    mock_generator,
    changes,
):
    conversation_id = save_quiz_discussion(
        app,
        topic=changes.get("conversation_topic", "Number Systems"),
    )

    payload = {
        "topic_slug": "number-systems",
        "conversation_id": conversation_id,
    }

    payload.update({
        key: value
        for key, value in changes.items()
        if key != "conversation_topic"
    })

    response = client.post(
        "/api/generated-quizzes",
        headers=student_headers,
        json=payload,
    )

    assert response.status_code == 409
    mock_generator.assert_not_called()


@pytest.mark.parametrize(
    "messages",
    [
        [],
        [("student", "Explain binary.")],
        [("assistant", "Hello.")],
    ],
)
def test_discussion_quiz_requires_question_and_reply(
    app,
    client,
    student_headers,
    number_systems_topic,
    mock_generator,
    messages,
):
    conversation_id = save_quiz_discussion(app, messages=messages)

    response = client.post(
        "/api/generated-quizzes",
        headers=student_headers,
        json={
            "topic_slug": "number-systems",
            "conversation_id": conversation_id,
        },
    )

    assert response.status_code == 400
    mock_generator.assert_not_called()

    with app.app_context():
        assert db.session.scalar(db.select(GeneratedQuiz.id)) is None


def test_discussion_quiz_uses_recent_messages_in_order(
    app,
    client,
    student_headers,
    number_systems_topic,
    mock_generator,
):
    messages = [
        ("student" if index % 2 == 0 else "assistant", f"Message {index}")
        for index in range(8)
    ]

    conversation_id = save_quiz_discussion(app, messages=messages)

    response = client.post(
        "/api/generated-quizzes",
        headers=student_headers,
        json={
            "topic_slug": "number-systems",
            "conversation_id": conversation_id,
        },
    )

    assert response.status_code == 201

    expected_context = "\n\n".join(
        f"{role}: {content}"
        for role, content in messages[-6:]
    )

    mock_generator.assert_called_once()
    assert (
        mock_generator.call_args.kwargs["discussion_context"]
        == expected_context
    )


@pytest.mark.parametrize("academic_level", ["ssc", "hsc"])
def test_ict_subject_quiz_uses_matching_level_discussion(
    app,
    client,
    mock_generator,
    academic_level,
):
    email = f"{academic_level}-discussion@example.com"
    headers = login_as(
        client,
        email=email,
        academic_level=academic_level,
    )

    with app.app_context():
        topic = Topic(
            title=f"{academic_level.upper()} ICT",
            slug=f"{academic_level}-ict",
            description="Subject discussion test.",
            display_order=1,
            subject="ict",
            academic_level=academic_level,
        )
        db.session.add(topic)
        db.session.commit()

    conversation_id = save_quiz_discussion(
        app,
        email=email,
        topic=f"{academic_level.upper()} ICT",
        messages=[
            ("student", "Save ar Save As-er difference ki?"),
            ("assistant", "Save updates; Save As allows another filename."),
        ],
    )

    response = client.post(
        "/api/generated-quizzes",
        headers=headers,
        json={
            "topic_slug": f"{academic_level}-ict",
            "conversation_id": conversation_id,
        },
    )

    assert response.status_code == 201
    quiz = response.get_json()["quiz"]
    assert quiz["topic"]["academic_level"] == academic_level
    assert quiz["practice_topic"] == "Save ar Save As-er difference ki?"
    assert_answers_are_hidden(quiz)

    mock_generator.assert_called_once()
    arguments = mock_generator.call_args.kwargs
    assert arguments["subject"] == "ict"
    assert arguments["academic_level"] == academic_level
    assert "Save ar Save As" in arguments["discussion_context"]

    # A broad subject quiz must have a saved discussion.
    mock_generator.reset_mock()

    without_discussion = client.post(
        "/api/generated-quizzes",
        headers=headers,
        json={"topic_slug": f"{academic_level}-ict"},
    )

    assert without_discussion.status_code == 400
    mock_generator.assert_not_called()


@pytest.fixture()
def ssc_save_topic(app):
    with app.app_context():
        topic = Topic(
            title="Save and Save As",
            slug="ssc-ict-save-and-save-as",
            description="Document saving practice.",
            display_order=12,
            subject="ict",
            academic_level="ssc",
        )
        db.session.add(topic)
        db.session.commit()
        return topic.id


@pytest.mark.parametrize(
    "learning_mode",
    ["personal_growth", "exam_preparation"],
)
def test_selected_ssc_lesson_generates_reloads_and_submits_without_chat(
    app,
    client,
    ssc_save_topic,
    mock_generator,
    learning_mode,
):
    headers = login_as(
        client,
        email="selected-lesson@example.com",
        academic_level="ssc",
    )

    response = client.post(
        "/api/generated-quizzes",
        headers=headers,
        json={
            "topic_slug": "ssc-ict-save-and-save-as",
            "response_language": "english",
            "learning_mode": learning_mode,
        },
    )

    assert response.status_code == 201
    quiz = response.get_json()["quiz"]

    assert quiz["practice_topic"] == "Save and Save As"
    assert quiz["topic"]["id"] == ssc_save_topic
    assert quiz["topic"]["academic_level"] == "ssc"
    assert_answers_are_hidden(quiz)

    # Exact arguments prove no discussion_context was forwarded.
    mock_generator.assert_called_once_with(
        topic_title="Save and Save As",
        response_language="english",
        learning_mode=learning_mode,
        subject="ict",
        academic_level="ssc",
    )
    with app.app_context():
        assert db.session.scalar(
            db.select(ChatConversation.id)
        ) is None

        saved = db.session.get(GeneratedQuiz, quiz["id"])
        assert saved is not None
        assert saved.practice_topic == "Save and Save As"
        assert saved.topic_id == ssc_save_topic
        assert saved.learning_mode == learning_mode

    loaded = client.get(
        f"/api/generated-quizzes/{quiz['id']}",
        headers=headers,
    )

    assert loaded.status_code == 200
    loaded_quiz = loaded.get_json()["quiz"]
    assert loaded_quiz["practice_topic"] == "Save and Save As"
    assert_answers_are_hidden(loaded_quiz)

    submitted = client.post(
        f"/api/generated-quizzes/{quiz['id']}/submit",
        headers=headers,
        json=answer_payload(),
    )

    assert submitted.status_code == 201
    result = submitted.get_json()
    assert result["attempt"]["score"] == 5
    assert result["attempt"]["total_questions"] == 5

    with app.app_context():
        attempt = db.session.get(
            QuizAttempt,
            result["attempt"]["id"],
        )
        assert attempt is not None
        assert attempt.topic_id == ssc_save_topic

    mock_generator.assert_called_once()


def test_hsc_student_cannot_generate_selected_ssc_lesson(
    app,
    client,
    student_headers,
    ssc_save_topic,
    mock_generator,
):
    response = client.post(
        "/api/generated-quizzes",
        headers=student_headers,
        json={"topic_slug": "ssc-ict-save-and-save-as"},
    )

    assert response.status_code == 403
    assert response.get_json()["code"] == "TOPIC_LEVEL_MISMATCH"
    mock_generator.assert_not_called()

    with app.app_context():
        assert db.session.scalar(
            db.select(GeneratedQuiz.id)
        ) is None


def test_unlisted_ssc_lesson_cannot_generate_quiz(
    app,
    client,
    mock_generator,
):
    headers = login_as(
        client,
        email="unsupported-lesson@example.com",
        academic_level="ssc",
    )

    with app.app_context():
        db.session.add(Topic(
            title="Untrained SSC Lesson",
            slug="ssc-ict-untrained-lesson",
            description="Not in the supported dataset.",
            display_order=30,
            subject="ict",
            academic_level="ssc",
        ))
        db.session.commit()

    response = client.post(
        "/api/generated-quizzes",
        headers=headers,
        json={"topic_slug": "ssc-ict-untrained-lesson"},
    )

    assert response.status_code == 400
    mock_generator.assert_not_called()

    with app.app_context():
        assert db.session.scalar(
            db.select(GeneratedQuiz.id)
        ) is None