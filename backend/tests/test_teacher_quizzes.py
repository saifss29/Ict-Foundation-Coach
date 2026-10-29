from unittest.mock import Mock
from copy import deepcopy

import pytest
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from models.teacher_quiz import TeacherQuiz
from models.topic import Topic
from models.user import User
from services.quiz_generator import QuizGenerationError


def login_as(client, app, *, role, email):
    registration_data = {
        "name": f"Quiz {role.title()}",
        "email": email,
        "password": "SecurePass123!",
        "role": role,
    }

    if role == "student":
        registration_data["academic_level"] = "hsc"

    response = client.post(
        "/api/auth/register",
        json=registration_data,
    )

    assert response.status_code == 201, response.get_json()
    user_id = response.get_json()["user"]["id"]

    with app.app_context():
        user = db.session.get(User, user_id)
        assert user is not None
        user.is_email_verified = True
        db.session.commit()

    response = client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": "SecurePass123!",
        },
    )

    assert response.status_code == 200

    return {
        "id": user_id,
        "headers": {
            "Authorization": (
                f"Bearer {response.get_json()['access_token']}"
            ),
        },
    }


def create_topic(app, slug="number-systems"):
    with app.app_context():
        topic = Topic(
            title=(
                "Number Systems"
                if slug == "number-systems"
                else "Logic Gates"
            ),
            slug=slug,
            description="Verified ICT practice topic.",
            display_order=1,
        )

        db.session.add(topic)
        db.session.commit()

        return topic.id


@pytest.fixture()
def generated_questions():
    return [
        {
            "id": str(index),
            "question_text": f"Practice question {index}",
            "option_a": "First option",
            "option_b": "Second option",
            "option_c": "Third option",
            "option_d": "Fourth option",
            "correct_option": "A",
            "explanation": "The first option is correct.",
        }
        for index in range(1, 6)
    ]


@pytest.fixture()
def generator_mock(monkeypatch, generated_questions):
    mock = Mock(return_value=generated_questions)

    monkeypatch.setattr(
        "routes.teacher_quizzes.generate_quiz",
        mock,
    )

    return mock


def create_draft(client, teacher, topic_id):
    response = client.post(
        "/api/teacher-quizzes",
        headers=teacher["headers"],
        json={
            "topic_id": topic_id,
            "title": "  Number Systems Practice  ",
            "response_language": "english",
        },
    )

    assert response.status_code == 201, response.get_json()

    return response.get_json()["quiz"]


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/teacher-quizzes"),
        ("GET", "/api/teacher-quizzes"),
        ("GET", "/api/teacher-quizzes/unknown"),
    ],
)
def test_teacher_quiz_routes_require_login(client, method, path):
    response = client.open(path, method=method)

    assert response.status_code == 401


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/teacher-quizzes"),
        ("GET", "/api/teacher-quizzes"),
        ("GET", "/api/teacher-quizzes/unknown"),
    ],
)
def test_student_cannot_access_teacher_quizzes(
    client, app, generator_mock, method, path
):
    student = login_as(
        client,
        app,
        role="student",
        email="student@example.com",
    )

    response = client.open(
        path,
        method=method,
        headers=student["headers"],
    )

    assert response.status_code == 403
    generator_mock.assert_not_called()


def test_teacher_can_generate_and_save_draft(
    client, app, generator_mock, generated_questions
):
    teacher = login_as(
        client,
        app,
        role="teacher",
        email="teacher@example.com",
    )
    topic_id = create_topic(app)

    quiz = create_draft(client, teacher, topic_id)

    assert quiz["teacher_id"] == teacher["id"]
    assert quiz["topic_id"] == topic_id
    assert quiz["title"] == "Number Systems Practice"
    assert quiz["status"] == "draft"
    assert quiz["published_at"] is None
    assert quiz["question_count"] == 5
    assert quiz["questions"] == generated_questions

    assert quiz["learning_mode"] == "personal_growth"

    generator_mock.assert_called_once_with(
        topic_title="Number Systems",
        response_language="english",
        learning_mode="personal_growth",
        subject="ict",
        academic_level="hsc",
    )

    with app.app_context():
        saved_quiz = db.session.get(TeacherQuiz, quiz["id"])

        assert saved_quiz is not None
        assert saved_quiz.teacher_id == teacher["id"]
        assert saved_quiz.questions == generated_questions
        assert saved_quiz.status == "draft"


def test_teacher_can_review_own_draft(
    client, app, generator_mock
):
    teacher = login_as(
        client,
        app,
        role="teacher",
        email="teacher@example.com",
    )
    quiz = create_draft(client, teacher, create_topic(app))

    response = client.get(
        f"/api/teacher-quizzes/{quiz['id']}",
        headers=teacher["headers"],
    )

    assert response.status_code == 200
    detail = response.get_json()["quiz"]

    assert detail["id"] == quiz["id"]
    assert detail["questions"][0]["correct_option"] == "A"
    assert detail["questions"][0]["explanation"]


def test_teacher_cannot_read_another_teachers_draft(
    client, app, generator_mock
):
    owner = login_as(
        client,
        app,
        role="teacher",
        email="owner@example.com",
    )
    other = login_as(
        client,
        app,
        role="teacher",
        email="other@example.com",
    )
    quiz = create_draft(client, owner, create_topic(app))

    response = client.get(
        f"/api/teacher-quizzes/{quiz['id']}",
        headers=other["headers"],
    )

    assert response.status_code == 404

    response = client.get(
        "/api/teacher-quizzes",
        headers=other["headers"],
    )

    assert response.status_code == 200
    assert response.get_json()["quizzes"] == []


def test_quiz_list_returns_summary_without_questions(
    client, app, generator_mock
):
    teacher = login_as(
        client,
        app,
        role="teacher",
        email="teacher@example.com",
    )
    quiz = create_draft(client, teacher, create_topic(app))

    response = client.get(
        "/api/teacher-quizzes",
        headers=teacher["headers"],
    )

    assert response.status_code == 200
    data = response.get_json()

    assert len(data["quizzes"]) == 1
    assert data["quizzes"][0]["id"] == quiz["id"]
    assert data["quizzes"][0]["question_count"] == 5
    assert "questions" not in data["quizzes"][0]
    assert data["pagination"]["has_more"] is False


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"topic_id": 1, "title": "   "},
        {"topic_id": 1, "title": "AB"},
        {"topic_id": 1, "title": "A" * 151},
        {"topic_id": True, "title": "Practice Quiz"},
        {"topic_id": "1", "title": "Practice Quiz"},
        {"topic_id": 0, "title": "Practice Quiz"},
        {
            "topic_id": 1,
            "title": "Practice Quiz",
            "response_language": "bangla",
        },
        {
            "topic_id": 1,
            "title": "Practice Quiz",
            "teacher_id": 999,
        },
    ],
)
def test_generation_rejects_invalid_input(
    client, app, generator_mock, payload
):
    teacher = login_as(
        client,
        app,
        role="teacher",
        email="teacher@example.com",
    )

    response = client.post(
        "/api/teacher-quizzes",
        headers=teacher["headers"],
        json=payload,
    )

    assert response.status_code == 400
    generator_mock.assert_not_called()


def test_generation_rejects_non_object_json(
    client, app, generator_mock
):
    teacher = login_as(
        client,
        app,
        role="teacher",
        email="teacher@example.com",
    )

    response = client.post(
        "/api/teacher-quizzes",
        headers=teacher["headers"],
        json=[],
    )

    assert response.status_code == 400
    generator_mock.assert_not_called()


def test_unknown_topic_is_rejected(client, app, generator_mock):
    teacher = login_as(
        client,
        app,
        role="teacher",
        email="teacher@example.com",
    )

    response = client.post(
        "/api/teacher-quizzes",
        headers=teacher["headers"],
        json={"topic_id": 999, "title": "Practice Quiz"},
    )

    assert response.status_code == 404
    generator_mock.assert_not_called()


def test_topic_without_ready_dataset_is_rejected(
    client, app, generator_mock
):
    teacher = login_as(
        client,
        app,
        role="teacher",
        email="teacher@example.com",
    )
    topic_id = create_topic(app, slug="logic-gates")

    response = client.post(
        "/api/teacher-quizzes",
        headers=teacher["headers"],
        json={"topic_id": topic_id, "title": "Logic Gates Practice"},
    )

    assert response.status_code == 400
    generator_mock.assert_not_called()


def test_generation_failure_does_not_save_draft(
    client, app, generator_mock
):
    teacher = login_as(
        client,
        app,
        role="teacher",
        email="teacher@example.com",
    )
    topic_id = create_topic(app)

    generator_mock.side_effect = QuizGenerationError(
        "Quiz generation took too long. Please try again.",
        status_code=504,
    )

    response = client.post(
        "/api/teacher-quizzes",
        headers=teacher["headers"],
        json={"topic_id": topic_id, "title": "Practice Quiz"},
    )

    assert response.status_code == 504

    with app.app_context():
        assert db.session.scalar(
            db.select(db.func.count()).select_from(TeacherQuiz)
        ) == 0


def test_database_failure_rolls_back_draft(
    client, app, generator_mock, monkeypatch
):
    teacher = login_as(
        client,
        app,
        role="teacher",
        email="teacher@example.com",
    )
    topic_id = create_topic(app)

    with monkeypatch.context() as patch:
        patch.setattr(
            db.session,
            "commit",
            Mock(side_effect=SQLAlchemyError("Test database failure")),
        )

        response = client.post(
            "/api/teacher-quizzes",
            headers=teacher["headers"],
            json={"topic_id": topic_id, "title": "Practice Quiz"},
        )

    assert response.status_code == 500

    with app.app_context():
        assert db.session.scalar(
            db.select(db.func.count()).select_from(TeacherQuiz)
        ) == 0


@pytest.mark.parametrize("page", ["0", "-1", "abc", "10001"])
def test_quiz_list_rejects_invalid_page(client, app, page):
    teacher = login_as(
        client,
        app,
        role="teacher",
        email="teacher@example.com",
    )

    response = client.get(
        f"/api/teacher-quizzes?page={page}",
        headers=teacher["headers"],
    )

    assert response.status_code == 400


@pytest.fixture()
def editable_draft(client, app, generator_mock):
    teacher = login_as(
        client,
        app,
        role="teacher",
        email="editor@example.com",
    )
    quiz = create_draft(client, teacher, create_topic(app))

    return teacher, quiz


def edit_payload(quiz):
    return {
        "title": "Updated Number Systems Quiz",
        "questions": deepcopy(quiz["questions"]),
    }


def assert_quiz_unchanged(app, original):
    with app.app_context():
        saved = db.session.get(TeacherQuiz, original["id"])

        assert saved is not None
        assert saved.title == original["title"]
        assert saved.questions == original["questions"]
        assert saved.status == original["status"]
        assert saved.published_at is None
        assert saved.updated_at.isoformat() == original["updated_at"]


@pytest.mark.parametrize("action", ["edit", "publish"])
def test_edit_publish_require_login(client, action):
    response = client.open(
        "/api/teacher-quizzes/unknown"
        + ("/publish" if action == "publish" else ""),
        method="POST" if action == "publish" else "PUT",
        json={},
    )

    assert response.status_code == 401


@pytest.mark.parametrize("action", ["edit", "publish"])
def test_student_cannot_edit_or_publish(
    client, app, editable_draft, action
):
    _, quiz = editable_draft
    student = login_as(
        client,
        app,
        role="student",
        email="quiz-student@example.com",
    )

    response = client.open(
        f"/api/teacher-quizzes/{quiz['id']}"
        + ("/publish" if action == "publish" else ""),
        method="POST" if action == "publish" else "PUT",
        headers=student["headers"],
        json={} if action == "publish" else edit_payload(quiz),
    )

    assert response.status_code == 403
    assert_quiz_unchanged(app, quiz)


@pytest.mark.parametrize("action", ["edit", "publish"])
@pytest.mark.parametrize("target", ["another-owner", "missing"])
def test_edit_publish_reject_inaccessible_quiz(
    client, app, editable_draft, action, target
):
    owner, quiz = editable_draft

    if target == "another-owner":
        teacher = login_as(
            client,
            app,
            role="teacher",
            email="other-editor@example.com",
        )
        quiz_id = quiz["id"]
    else:
        teacher = owner
        quiz_id = "00000000-0000-0000-0000-000000000000"

    response = client.open(
        f"/api/teacher-quizzes/{quiz_id}"
        + ("/publish" if action == "publish" else ""),
        method="POST" if action == "publish" else "PUT",
        headers=teacher["headers"],
        json={} if action == "publish" else edit_payload(quiz),
    )

    assert response.status_code == 404
    assert_quiz_unchanged(app, quiz)


def test_owner_can_edit_draft_and_persist_full_questions(
    client, app, editable_draft, generator_mock
):
    teacher, quiz = editable_draft
    payload = edit_payload(quiz)
    payload["title"] = "  Updated Number Systems Quiz  "
    payload["questions"][0].update({
        "question_text": "  What is the base of binary?  ",
        "option_a": "  2  ",
        "option_b": "8",
        "option_c": "10",
        "option_d": "16",
        "correct_option": "  A  ",
        "explanation": "  Binary uses base 2.  ",
    })
    payload["questions"].reverse()
    generator_mock.reset_mock()

    response = client.put(
        f"/api/teacher-quizzes/{quiz['id']}",
        headers=teacher["headers"],
        json=payload,
    )

    assert response.status_code == 200
    updated = response.get_json()["quiz"]

    assert updated["title"] == "Updated Number Systems Quiz"
    assert updated["status"] == "draft"
    assert updated["published_at"] is None
    assert updated["question_count"] == 5
    assert [q["id"] for q in updated["questions"]] == [
        "1", "2", "3", "4", "5"
    ]
    assert updated["questions"][0]["question_text"] == (
        "What is the base of binary?"
    )
    assert updated["questions"][0]["option_a"] == "2"
    assert updated["questions"][0]["correct_option"] == "A"
    assert updated["questions"][0]["explanation"] == (
        "Binary uses base 2."
    )
    assert updated["teacher_id"] == quiz["teacher_id"]
    assert updated["topic_id"] == quiz["topic_id"]
    assert updated["response_language"] == quiz["response_language"]
    assert updated["created_at"] == quiz["created_at"]
    generator_mock.assert_not_called()

    with app.app_context():
        saved = db.session.get(TeacherQuiz, quiz["id"])

        assert saved is not None
        assert saved.title == updated["title"]
        assert saved.questions == updated["questions"]
        assert saved.updated_at.isoformat() == updated["updated_at"]


@pytest.mark.parametrize(
    "invalid_case",
    [
        "missing-title",
        "missing-questions",
        "blank-title",
        "long-title",
        "four-questions",
        "six-questions",
        "duplicate-id",
        "integer-id",
        "duplicate-question",
        "duplicate-options",
        "blank-question",
        "invalid-answer",
        "missing-explanation",
        "unknown-question-field",
        "unknown-top-level-field",
    ],
)
def test_edit_rejects_invalid_payload_without_changing_draft(
    client, app, editable_draft, invalid_case
):
    teacher, quiz = editable_draft
    payload = edit_payload(quiz)
    questions = payload["questions"]

    if invalid_case == "missing-title":
        del payload["title"]
    elif invalid_case == "missing-questions":
        del payload["questions"]
    elif invalid_case == "blank-title":
        payload["title"] = "   "
    elif invalid_case == "long-title":
        payload["title"] = "A" * 151
    elif invalid_case == "four-questions":
        questions.pop()
    elif invalid_case == "six-questions":
        questions.append(deepcopy(questions[0]))
    elif invalid_case == "duplicate-id":
        questions[1]["id"] = questions[0]["id"]
    elif invalid_case == "integer-id":
        questions[0]["id"] = 1
    elif invalid_case == "duplicate-question":
        questions[1]["question_text"] = (
            "  " + questions[0]["question_text"].upper() + "  "
        )
    elif invalid_case == "duplicate-options":
        questions[0]["option_b"] = (
            "  " + questions[0]["option_a"].upper() + "  "
        )
    elif invalid_case == "blank-question":
        questions[0]["question_text"] = "   "
    elif invalid_case == "invalid-answer":
        questions[0]["correct_option"] = "E"
    elif invalid_case == "missing-explanation":
        del questions[0]["explanation"]
    elif invalid_case == "unknown-question-field":
        questions[0]["extra"] = "Unexpected"
    elif invalid_case == "unknown-top-level-field":
        payload["teacher_id"] = 999

    response = client.put(
        f"/api/teacher-quizzes/{quiz['id']}",
        headers=teacher["headers"],
        json=payload,
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Validation failed"
    assert response.get_json()["messages"]
    assert_quiz_unchanged(app, quiz)


@pytest.mark.parametrize("action", ["edit", "publish"])
@pytest.mark.parametrize(
    "body",
    ["", "null", "[]", '"text"', "{invalid"],
)
def test_edit_publish_reject_invalid_json_body(
    client, app, editable_draft, action, body
):
    teacher, quiz = editable_draft

    response = client.open(
        f"/api/teacher-quizzes/{quiz['id']}"
        + ("/publish" if action == "publish" else ""),
        method="POST" if action == "publish" else "PUT",
        headers=teacher["headers"],
        data=body,
        content_type="application/json",
    )

    assert response.status_code == 400
    assert_quiz_unchanged(app, quiz)


def test_owner_can_publish_saved_draft(
    client, app, editable_draft, generator_mock
):
    teacher, quiz = editable_draft
    payload = edit_payload(quiz)
    payload["questions"][0]["correct_option"] = "B"

    response = client.put(
        f"/api/teacher-quizzes/{quiz['id']}",
        headers=teacher["headers"],
        json=payload,
    )
    assert response.status_code == 200
    edited = response.get_json()["quiz"]
    generator_mock.reset_mock()

    response = client.post(
        f"/api/teacher-quizzes/{quiz['id']}/publish",
        headers=teacher["headers"],
        json={},
    )

    assert response.status_code == 200
    published = response.get_json()["quiz"]

    assert published["status"] == "published"
    assert published["published_at"] is not None
    assert published["updated_at"] == published["published_at"]
    assert published["questions"] == edited["questions"]
    assert published["title"] == edited["title"]
    assert published["created_at"] == quiz["created_at"]
    generator_mock.assert_not_called()

    with app.app_context():
        saved = db.session.get(TeacherQuiz, quiz["id"])

        assert saved is not None
        assert saved.status == "published"
        assert saved.questions == edited["questions"]
        assert saved.published_at.isoformat() == (
            published["published_at"]
        )


def test_publish_rejects_nonempty_object(
    client, app, editable_draft
):
    teacher, quiz = editable_draft

    response = client.post(
        f"/api/teacher-quizzes/{quiz['id']}/publish",
        headers=teacher["headers"],
        json={"title": "Unexpected edit"},
    )

    assert response.status_code == 400
    assert_quiz_unchanged(app, quiz)


@pytest.mark.parametrize("invalid_saved_data", ["title", "questions"])
def test_publish_revalidates_saved_draft(
    client, app, editable_draft, invalid_saved_data
):
    teacher, quiz = editable_draft

    with app.app_context():
        saved = db.session.get(TeacherQuiz, quiz["id"])
        assert saved is not None

        if invalid_saved_data == "title":
            saved.title = "AB"
        else:
            saved.questions = deepcopy(quiz["questions"][:4])

        db.session.commit()
        invalid_title = saved.title
        invalid_questions = deepcopy(saved.questions)
        previous_updated_at = saved.updated_at

    response = client.post(
        f"/api/teacher-quizzes/{quiz['id']}/publish",
        headers=teacher["headers"],
        json={},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == (
        "Quiz draft is invalid. Review it before publishing."
    )
    assert response.get_json()["messages"]

    with app.app_context():
        saved = db.session.get(TeacherQuiz, quiz["id"])

        assert saved is not None
        assert saved.status == "draft"
        assert saved.published_at is None
        assert saved.title == invalid_title
        assert saved.questions == invalid_questions
        assert saved.updated_at == previous_updated_at


@pytest.mark.parametrize("action", ["edit", "publish"])
def test_published_quiz_rejects_edit_and_repeat_publish(
    client, app, editable_draft, action
):
    teacher, quiz = editable_draft
    response = client.post(
        f"/api/teacher-quizzes/{quiz['id']}/publish",
        headers=teacher["headers"],
        json={},
    )
    assert response.status_code == 200
    published = response.get_json()["quiz"]

    response = client.open(
        f"/api/teacher-quizzes/{quiz['id']}"
        + ("/publish" if action == "publish" else ""),
        method="POST" if action == "publish" else "PUT",
        headers=teacher["headers"],
        json={} if action == "publish" else edit_payload(quiz),
    )

    assert response.status_code == 409

    with app.app_context():
        saved = db.session.get(TeacherQuiz, quiz["id"])

        assert saved is not None
        assert saved.status == "published"
        assert saved.title == published["title"]
        assert saved.questions == published["questions"]
        assert saved.published_at.isoformat() == (
            published["published_at"]
        )
        assert saved.updated_at.isoformat() == published["updated_at"]


@pytest.mark.parametrize(
    ("action", "expected_error"),
    [
        ("edit", "Could not update quiz draft. Try again later."),
        ("publish", "Could not publish quiz. Try again later."),
    ],
)
def test_edit_publish_database_failure_preserves_draft(
    client, app, editable_draft, monkeypatch, action, expected_error
):
    teacher, quiz = editable_draft

    with monkeypatch.context() as patch:
        patch.setattr(
            db.session,
            "commit",
            Mock(side_effect=SQLAlchemyError("Test database failure")),
        )

        response = client.open(
            f"/api/teacher-quizzes/{quiz['id']}"
            + ("/publish" if action == "publish" else ""),
            method="POST" if action == "publish" else "PUT",
            headers=teacher["headers"],
            json={} if action == "publish" else edit_payload(quiz),
        )

    assert response.status_code == 500
    assert response.get_json()["error"] == expected_error
    assert_quiz_unchanged(app, quiz)

    # A retry must work after the failed transaction was rolled back.
    response = client.open(
        f"/api/teacher-quizzes/{quiz['id']}"
        + ("/publish" if action == "publish" else ""),
        method="POST" if action == "publish" else "PUT",
        headers=teacher["headers"],
        json={} if action == "publish" else edit_payload(quiz),
    )

    assert response.status_code == 200


def make_teacher_count_questions(count):
    return [
        {
            "id": str(index),
            "question_text": f"Selected-count question {index}",
            "option_a": "2",
            "option_b": "8",
            "option_c": "10",
            "option_d": "16",
            "correct_option": "A",
            "explanation": "Binary uses base 2.",
        }
        for index in range(1, count + 1)
    ]


def create_selected_count_draft(
    client,
    app,
    generator_mock,
    count,
):
    teacher = login_as(
        client,
        app,
        role="teacher",
        email="count-teacher@example.com",
    )
    topic_id = create_topic(app)
    questions = make_teacher_count_questions(count)
    generator_mock.return_value = questions

    response = client.post(
        "/api/teacher-quizzes",
        headers=teacher["headers"],
        json={
            "topic_id": topic_id,
            "title": "Selected Count Quiz",
            "response_language": "english",
            "question_count": count,
        },
    )

    assert response.status_code == 201
    return teacher, response.get_json()["quiz"]


@pytest.mark.parametrize("count", [1, 10, 20])
def test_teacher_selected_count_is_generated_and_saved(
    client,
    app,
    generator_mock,
    count,
):
    teacher, quiz = create_selected_count_draft(
        client,
        app,
        generator_mock,
        count,
    )

    assert quiz["learning_mode"] == "personal_growth"

    generator_mock.assert_called_once_with(
        topic_title="Number Systems",
        response_language="english",
        question_count=count,
        learning_mode="personal_growth",
        subject="ict",
        academic_level="hsc",
    )

    assert quiz["question_count"] == count
    assert len(quiz["questions"]) == count

    with app.app_context():
        saved = db.session.get(TeacherQuiz, quiz["id"])

        assert saved is not None
        assert saved.question_count == count
        assert saved.questions == quiz["questions"]

    detail_response = client.get(
        f"/api/teacher-quizzes/{quiz['id']}",
        headers=teacher["headers"],
    )
    assert detail_response.status_code == 200
    assert detail_response.get_json()["quiz"]["question_count"] == count

    list_response = client.get(
        "/api/teacher-quizzes",
        headers=teacher["headers"],
    )
    assert list_response.status_code == 200
    summary = list_response.get_json()["quizzes"][0]
    assert summary["question_count"] == count
    assert "questions" not in summary


@pytest.mark.parametrize(
    "count",
    [True, False, "10", 10.0, None, 0, -1, 21],
)
def test_teacher_generation_rejects_invalid_selected_count(
    client,
    app,
    generator_mock,
    count,
):
    teacher = login_as(
        client,
        app,
        role="teacher",
        email="invalid-count@example.com",
    )
    topic_id = create_topic(app)

    response = client.post(
        "/api/teacher-quizzes",
        headers=teacher["headers"],
        json={
            "topic_id": topic_id,
            "title": "Practice Quiz",
            "question_count": count,
        },
    )

    assert response.status_code == 400
    assert "question_count" in response.get_json()["messages"]
    generator_mock.assert_not_called()

    with app.app_context():
        assert db.session.scalar(
            db.select(db.func.count()).select_from(TeacherQuiz)
        ) == 0


def test_teacher_generation_rejects_wrong_generated_count(
    client,
    app,
    generator_mock,
):
    teacher = login_as(
        client,
        app,
        role="teacher",
        email="wrong-count@example.com",
    )
    topic_id = create_topic(app)

    # Simulate a service returning fewer questions than requested.
    generator_mock.return_value = make_teacher_count_questions(5)

    response = client.post(
        "/api/teacher-quizzes",
        headers=teacher["headers"],
        json={
            "topic_id": topic_id,
            "title": "Ten Question Quiz",
            "question_count": 10,
        },
    )

    assert response.status_code == 502

    with app.app_context():
        assert db.session.scalar(
            db.select(db.func.count()).select_from(TeacherQuiz)
        ) == 0


@pytest.mark.parametrize("count", [1, 10, 20])
def test_teacher_can_edit_and_publish_selected_count(
    client,
    app,
    generator_mock,
    count,
):
    teacher, quiz = create_selected_count_draft(
        client,
        app,
        generator_mock,
        count,
    )
    payload = edit_payload(quiz)
    payload["questions"][0]["correct_option"] = "B"
    payload["questions"].reverse()
    generator_mock.reset_mock()

    response = client.put(
        f"/api/teacher-quizzes/{quiz['id']}",
        headers=teacher["headers"],
        json=payload,
    )

    assert response.status_code == 200
    edited = response.get_json()["quiz"]
    assert edited["question_count"] == count
    assert [q["id"] for q in edited["questions"]] == [
        str(index) for index in range(1, count + 1)
    ]
    assert edited["questions"][0]["correct_option"] == "B"

    response = client.post(
        f"/api/teacher-quizzes/{quiz['id']}/publish",
        headers=teacher["headers"],
        json={},
    )

    assert response.status_code == 200
    published = response.get_json()["quiz"]
    assert published["status"] == "published"
    assert published["question_count"] == count
    assert published["questions"] == edited["questions"]
    generator_mock.assert_not_called()

    with app.app_context():
        saved = db.session.get(TeacherQuiz, quiz["id"])

        assert saved is not None
        assert saved.question_count == count
        assert saved.questions == published["questions"]
        assert saved.status == "published"
        assert saved.published_at is not None


@pytest.mark.parametrize("submitted_count", [9, 11])
def test_edit_cannot_change_saved_question_count(
    client,
    app,
    generator_mock,
    submitted_count,
):
    teacher, quiz = create_selected_count_draft(
        client,
        app,
        generator_mock,
        10,
    )
    payload = edit_payload(quiz)
    payload["questions"] = make_teacher_count_questions(submitted_count)

    response = client.put(
        f"/api/teacher-quizzes/{quiz['id']}",
        headers=teacher["headers"],
        json=payload,
    )

    assert response.status_code == 400
    assert_quiz_unchanged(app, quiz)

    with app.app_context():
        saved = db.session.get(TeacherQuiz, quiz["id"])
        assert saved is not None
        assert saved.question_count == 10


def test_edit_rejects_question_count_override(
    client,
    app,
    generator_mock,
):
    teacher, quiz = create_selected_count_draft(
        client,
        app,
        generator_mock,
        10,
    )
    payload = edit_payload(quiz)
    payload["question_count"] = 5

    response = client.put(
        f"/api/teacher-quizzes/{quiz['id']}",
        headers=teacher["headers"],
        json=payload,
    )

    assert response.status_code == 400
    assert "question_count" in response.get_json()["messages"]
    assert_quiz_unchanged(app, quiz)


def test_publish_checks_saved_count_against_saved_questions(
    client,
    app,
    generator_mock,
):
    teacher, quiz = create_selected_count_draft(
        client,
        app,
        generator_mock,
        10,
    )

    with app.app_context():
        saved = db.session.get(TeacherQuiz, quiz["id"])
        assert saved is not None

        # Simulate damaged saved data: expected 10, actual 9.
        saved.questions = deepcopy(quiz["questions"][:9])
        db.session.commit()

    response = client.post(
        f"/api/teacher-quizzes/{quiz['id']}/publish",
        headers=teacher["headers"],
        json={},
    )

    assert response.status_code == 400
    assert response.get_json()["messages"]

    with app.app_context():
        saved = db.session.get(TeacherQuiz, quiz["id"])

        assert saved is not None
        assert saved.question_count == 10
        assert len(saved.questions) == 9
        assert saved.status == "draft"
        assert saved.published_at is None


@pytest.mark.parametrize(
    "learning_mode",
    ["personal_growth", "exam_preparation"],
)
@pytest.mark.parametrize("count", [5, 10])
def test_teacher_quiz_mode_persists_through_edit_and_publish(
    client,
    app,
    generator_mock,
    learning_mode,
    count,
):
    teacher = login_as(
        client,
        app,
        role="teacher",
        email="mode-teacher@example.com",
    )
    topic_id = create_topic(app)
    generator_mock.return_value = make_teacher_count_questions(count)

    response = client.post(
        "/api/teacher-quizzes",
        headers=teacher["headers"],
        json={
            "topic_id": topic_id,
            "title": "Learning Mode Practice",
            "response_language": "english",
            "question_count": count,
            "learning_mode": learning_mode,
        },
    )

    assert response.status_code == 201
    quiz = response.get_json()["quiz"]
    assert quiz["learning_mode"] == learning_mode

    expected_arguments = {
        "topic_title": "Number Systems",
        "response_language": "english",
        "learning_mode": learning_mode,
        "subject": "ict",
        "academic_level": "hsc",
    }

    if count != 5:
        expected_arguments["question_count"] = count

    generator_mock.assert_called_once_with(**expected_arguments)

    with app.app_context():
        saved = db.session.get(TeacherQuiz, quiz["id"])
        assert saved is not None
        assert saved.learning_mode == learning_mode

    detail_response = client.get(
        f"/api/teacher-quizzes/{quiz['id']}",
        headers=teacher["headers"],
    )

    assert detail_response.status_code == 200
    assert detail_response.get_json()["quiz"]["learning_mode"] == learning_mode

    list_response = client.get(
        "/api/teacher-quizzes",
        headers=teacher["headers"],
    )

    assert list_response.status_code == 200
    summary = next(
        item
        for item in list_response.get_json()["quizzes"]
        if item["id"] == quiz["id"]
    )
    assert summary["learning_mode"] == learning_mode
    assert "questions" not in summary

    generator_mock.reset_mock()

    edit_response = client.put(
        f"/api/teacher-quizzes/{quiz['id']}",
        headers=teacher["headers"],
        json=edit_payload(quiz),
    )

    assert edit_response.status_code == 200
    assert edit_response.get_json()["quiz"]["learning_mode"] == learning_mode

    publish_response = client.post(
        f"/api/teacher-quizzes/{quiz['id']}/publish",
        headers=teacher["headers"],
        json={},
    )

    assert publish_response.status_code == 200
    published = publish_response.get_json()["quiz"]
    assert published["status"] == "published"
    assert published["learning_mode"] == learning_mode
    generator_mock.assert_not_called()

    reload_response = client.get(
        f"/api/teacher-quizzes/{quiz['id']}",
        headers=teacher["headers"],
    )

    assert reload_response.status_code == 200
    assert reload_response.get_json()["quiz"]["learning_mode"] == learning_mode

    with app.app_context():
        saved = db.session.get(TeacherQuiz, quiz["id"])
        assert saved is not None
        assert saved.learning_mode == learning_mode
        assert saved.status == "published"


@pytest.mark.parametrize(
    "learning_mode",
    [
        "",
        "exam",
        "EXAM_PREPARATION",
        " personal_growth ",
        None,
        True,
        1,
        [],
        {},
    ],
)
def test_teacher_generation_rejects_invalid_learning_mode(
    client,
    app,
    generator_mock,
    learning_mode,
):
    teacher = login_as(
        client,
        app,
        role="teacher",
        email="invalid-mode@example.com",
    )
    topic_id = create_topic(app)

    response = client.post(
        "/api/teacher-quizzes",
        headers=teacher["headers"],
        json={
            "topic_id": topic_id,
            "title": "Invalid Mode Practice",
            "learning_mode": learning_mode,
        },
    )

    assert response.status_code == 400
    assert "learning_mode" in response.get_json()["messages"]
    generator_mock.assert_not_called()

    with app.app_context():
        assert db.session.scalar(
            db.select(db.func.count()).select_from(TeacherQuiz)
        ) == 0

def test_remove_moves_teacher_quiz_to_history(
    client, app, editable_draft
):
    teacher, quiz = editable_draft

    response = client.patch(
        f"/api/teacher-quizzes/{quiz['id']}/remove",
        headers=teacher["headers"],
        json={},
    )
    assert response.status_code == 200

    active = client.get(
        "/api/teacher-quizzes",
        headers=teacher["headers"],
    )
    assert active.status_code == 200
    assert active.get_json()["quizzes"] == []

    history = client.get(
        "/api/teacher-quizzes?view=history",
        headers=teacher["headers"],
    )
    assert history.status_code == 200
    summaries = history.get_json()["quizzes"]
    assert [item["id"] for item in summaries] == [quiz["id"]]
    assert "questions" not in summaries[0]

    detail = client.get(
        f"/api/teacher-quizzes/{quiz['id']}",
        headers=teacher["headers"],
    )
    assert detail.status_code == 200
    assert detail.get_json()["quiz"]["questions"] == quiz["questions"]
    assert detail.get_json()["quiz"]["status"] == "draft"

    with app.app_context():
        saved = db.session.get(TeacherQuiz, quiz["id"])
        assert saved is not None
        assert saved.removed_at is not None
        assert saved.title == quiz["title"]
        assert saved.questions == quiz["questions"]


def test_remove_preserves_other_active_quizzes(
    client, editable_draft, generator_mock
):
    teacher, first = editable_draft
    second = create_draft(client, teacher, first["topic_id"])

    response = client.patch(
        f"/api/teacher-quizzes/{first['id']}/remove",
        headers=teacher["headers"],
        json={},
    )
    assert response.status_code == 200

    active = client.get(
        "/api/teacher-quizzes?view=active",
        headers=teacher["headers"],
    )
    assert active.status_code == 200
    assert [
        item["id"] for item in active.get_json()["quizzes"]
    ] == [second["id"]]


def test_repeated_quiz_remove_preserves_removal_time(
    client, app, editable_draft
):
    teacher, quiz = editable_draft
    path = f"/api/teacher-quizzes/{quiz['id']}/remove"

    response = client.patch(
        path, headers=teacher["headers"], json={}
    )
    assert response.status_code == 200

    with app.app_context():
        saved = db.session.get(TeacherQuiz, quiz["id"])
        assert saved is not None
        first_removed_at = saved.removed_at

    response = client.patch(
        path, headers=teacher["headers"], json={}
    )
    assert response.status_code == 200

    with app.app_context():
        saved = db.session.get(TeacherQuiz, quiz["id"])
        assert saved is not None
        assert saved.removed_at == first_removed_at


@pytest.mark.parametrize(
    ("role", "expected_status"),
    [("teacher", 404), ("student", 403)],
)
def test_quiz_remove_rejects_other_users(
    client, app, editable_draft, role, expected_status
):
    owner, quiz = editable_draft
    other = login_as(
        client,
        app,
        role=role,
        email=f"history-other-{role}@example.com",
    )

    response = client.patch(
        f"/api/teacher-quizzes/{quiz['id']}/remove",
        headers=other["headers"],
        json={},
    )
    assert response.status_code == expected_status

    with app.app_context():
        saved = db.session.get(TeacherQuiz, quiz["id"])
        assert saved is not None
        assert saved.removed_at is None

    if role == "teacher":
        response = client.get(
            "/api/teacher-quizzes?view=history",
            headers=other["headers"],
        )
        assert response.status_code == 200
        assert response.get_json()["quizzes"] == []


def test_quiz_remove_requires_login(client):
    response = client.patch(
        "/api/teacher-quizzes/unknown/remove",
        json={},
    )
    assert response.status_code == 401


def test_quiz_remove_rejects_missing_quiz(
    client, editable_draft
):
    teacher, _ = editable_draft

    response = client.patch(
        "/api/teacher-quizzes/unknown/remove",
        headers=teacher["headers"],
        json={},
    )
    assert response.status_code == 404


@pytest.mark.parametrize(
    "payload",
    [[], "remove", {"teacher_id": 999}],
)
def test_quiz_remove_rejects_invalid_body(
    client, app, editable_draft, payload
):
    teacher, quiz = editable_draft

    response = client.patch(
        f"/api/teacher-quizzes/{quiz['id']}/remove",
        headers=teacher["headers"],
        json=payload,
    )
    assert response.status_code == 400

    with app.app_context():
        saved = db.session.get(TeacherQuiz, quiz["id"])
        assert saved is not None
        assert saved.removed_at is None


@pytest.mark.parametrize("view", ["", "deleted", "all"])
def test_quiz_list_rejects_invalid_history_view(
    client, editable_draft, view
):
    teacher, _ = editable_draft

    response = client.get(
        "/api/teacher-quizzes",
        headers=teacher["headers"],
        query_string={"view": view},
    )
    assert response.status_code == 400


def test_quiz_remove_database_failure_rolls_back(
    client, app, editable_draft, monkeypatch
):
    teacher, quiz = editable_draft

    with monkeypatch.context() as patch:
        patch.setattr(
            db.session,
            "commit",
            Mock(side_effect=SQLAlchemyError("Test failure")),
        )
        response = client.patch(
            f"/api/teacher-quizzes/{quiz['id']}/remove",
            headers=teacher["headers"],
            json={},
        )

    assert response.status_code == 500

    with app.app_context():
        saved = db.session.get(TeacherQuiz, quiz["id"])
        assert saved is not None
        assert saved.removed_at is None
        assert saved.questions == quiz["questions"]

    retry = client.patch(
        f"/api/teacher-quizzes/{quiz['id']}/remove",
        headers=teacher["headers"],
        json={},
    )
    assert retry.status_code == 200


def test_removed_draft_can_still_be_edited_and_published(
    client, editable_draft
):
    teacher, quiz = editable_draft

    response = client.patch(
        f"/api/teacher-quizzes/{quiz['id']}/remove",
        headers=teacher["headers"],
        json={},
    )
    assert response.status_code == 200

    response = client.put(
        f"/api/teacher-quizzes/{quiz['id']}",
        headers=teacher["headers"],
        json=edit_payload(quiz),
    )
    assert response.status_code == 200

    response = client.post(
        f"/api/teacher-quizzes/{quiz['id']}/publish",
        headers=teacher["headers"],
        json={},
    )
    assert response.status_code == 200
    assert response.get_json()["quiz"]["status"] == "published"

    active = client.get(
        "/api/teacher-quizzes",
        headers=teacher["headers"],
    )
    assert active.status_code == 200
    assert active.get_json()["quizzes"] == []

    history = client.get(
        "/api/teacher-quizzes?view=history",
        headers=teacher["headers"],
    )
    assert history.status_code == 200
    assert history.get_json()["quizzes"][0]["status"] == "published"