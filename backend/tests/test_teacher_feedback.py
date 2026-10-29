from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import pytest

from extensions import db
from models.quiz_attempt import QuizAttempt
from models.teacher_feedback import TeacherFeedback
from models.topic import Topic


def login_as(client, *, role, email):
    registration_data = {
        "name": f"Test {role.title()}",
        "email": email,
        "password": "SecurePass123!",
        "role": role,
    }

    if role == "student":
        registration_data["academic_level"] = "hsc"

    with patch(
        "services.email_verification_service.send_email"
    ) as mock_email:
        registration = client.post(
            "/api/auth/register",
            json=registration_data,
        )

        assert registration.status_code == 201
        mock_email.assert_called_once()

        body = mock_email.call_args.kwargs["body"]

    link = next(
        line.strip()
        for line in body.splitlines()
        if line.strip().startswith(
            "http://localhost:5173/verify-email?"
        )
    )

    token = parse_qs(urlsplit(link).query)["token"][0]

    verification = client.post(
        "/api/auth/verify-email",
        json={"token": token},
    )

    assert verification.status_code == 200

    login = client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": "SecurePass123!",
        },
    )

    assert login.status_code == 200

    data = login.get_json()

    return {
        "id": data["user"]["id"],
        "headers": {
            "Authorization": f"Bearer {data['access_token']}",
        },
    }


@pytest.fixture()
def feedback_setup(client):
    teacher = login_as(
        client,
        role="teacher",
        email="teacher@example.com",
    )

    student = login_as(
        client,
        role="student",
        email="student@example.com",
    )

    created = client.post(
        "/api/classes",
        headers=teacher["headers"],
        json={"name": "HSC ICT Batch A"},
    )

    assert created.status_code == 201

    classroom = created.get_json()["classroom"]

    joined = client.post(
        "/api/classes/join",
        headers=student["headers"],
        json={"join_code": classroom["join_code"]},
    )

    assert joined.status_code == 201

    return {
        "teacher": teacher,
        "student": student,
        "classroom": classroom,
        "path": (
            f"/api/feedback/classes/{classroom['id']}"
            f"/students/{student['id']}"
        ),
    }


def send_feedback(client, setup, **extra):
    response = client.post(
        setup["path"],
        headers=setup["teacher"]["headers"],
        json={
            "message": "Practice binary conversion again.",
            **extra,
        },
    )

    assert response.status_code == 201

    return response.get_json()["feedback"]


def create_attempt(app, student_id):
    with app.app_context():
        topic = Topic(
            title="Feedback Test Topic",
            slug="feedback-test-topic",
            description="Test quiz feedback.",
            display_order=1,
        )

        db.session.add(topic)
        db.session.flush()

        attempt = QuizAttempt(
            user_id=student_id,
            topic_id=topic.id,
            score=2,
            total_questions=5,
        )

        db.session.add(attempt)
        db.session.commit()

        return attempt.id


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/feedback/me"),
        ("GET", "/api/feedback/classes/1/students/1"),
        ("POST", "/api/feedback/classes/1/students/1"),
    ],
)
def test_feedback_routes_require_login(client, method, path):
    response = client.open(path, method=method, json={})

    assert response.status_code == 401


def test_teacher_can_send_and_list_feedback(client, app, feedback_setup):
    setup = feedback_setup

    response = client.post(
        setup["path"],
        headers=setup["teacher"]["headers"],
        json={"message": "  Practice binary conversion again.  "},
    )

    assert response.status_code == 201

    data = response.get_json()

    assert data["message"] == "Feedback sent successfully"

    feedback = data["feedback"]

    assert feedback["message"] == "Practice binary conversion again."
    assert feedback["teacher_id"] == setup["teacher"]["id"]
    assert feedback["student_id"] == setup["student"]["id"]
    assert feedback["classroom_id"] == setup["classroom"]["id"]
    assert feedback["teacher_name"] == "Test Teacher"
    assert feedback["classroom_name"] == "HSC ICT Batch A"
    assert feedback["attempt_id"] is None

    with app.app_context():
        saved = db.session.get(TeacherFeedback, feedback["id"])

        assert saved is not None
        assert saved.message == feedback["message"]

    teacher_list = client.get(
        setup["path"],
        headers=setup["teacher"]["headers"],
    )

    assert teacher_list.status_code == 200
    assert teacher_list.get_json()["feedback"] == [feedback]

    student_list = client.get(
        "/api/feedback/me",
        headers=setup["student"]["headers"],
    )

    assert student_list.status_code == 200
    assert student_list.get_json()["feedback"] == [feedback]


def test_feedback_can_link_students_quiz_attempt(
    client,
    app,
    feedback_setup,
):
    attempt_id = create_attempt(
        app,
        feedback_setup["student"]["id"],
    )

    feedback = send_feedback(
        client,
        feedback_setup,
        attempt_id=attempt_id,
    )

    assert feedback["attempt_id"] == attempt_id


def test_feedback_rejects_another_students_attempt(
    client,
    app,
    feedback_setup,
):
    other_student = login_as(
        client,
        role="student",
        email="other@example.com",
    )

    attempt_id = create_attempt(app, other_student["id"])

    response = client.post(
        feedback_setup["path"],
        headers=feedback_setup["teacher"]["headers"],
        json={
            "message": "Check this quiz.",
            "attempt_id": attempt_id,
        },
    )

    assert response.status_code == 404

    with app.app_context():
        assert db.session.scalar(
            db.select(TeacherFeedback.id)
        ) is None


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_student_cannot_access_teacher_feedback_routes(
    client,
    feedback_setup,
    method,
):
    response = client.open(
        feedback_setup["path"],
        method=method,
        headers=feedback_setup["student"]["headers"],
        json={"message": "Unauthorized feedback"},
    )

    assert response.status_code == 403


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_teacher_cannot_access_another_teachers_class(
    client,
    feedback_setup,
    method,
):
    other_teacher = login_as(
        client,
        role="teacher",
        email="other.teacher@example.com",
    )

    response = client.open(
        feedback_setup["path"],
        method=method,
        headers=other_teacher["headers"],
        json={"message": "Unauthorized feedback"},
    )

    assert response.status_code == 403


def test_student_only_sees_own_feedback(client, feedback_setup):
    send_feedback(client, feedback_setup)

    other_student = login_as(
        client,
        role="student",
        email="other@example.com",
    )

    response = client.get(
        "/api/feedback/me",
        headers=other_student["headers"],
    )

    assert response.status_code == 200
    assert response.get_json()["feedback"] == []


def test_teacher_cannot_use_student_feedback_feed(client, feedback_setup):
    response = client.get(
        "/api/feedback/me",
        headers=feedback_setup["teacher"]["headers"],
    )

    assert response.status_code == 403


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"message": "   "},
        {"message": None},
        {"message": 123},
        {"message": "A" * 2001},
        {"message": "Practice again.", "attempt_id": 0},
        {"message": "Practice again.", "attempt_id": "1"},
        {"message": "Practice again.", "teacher_id": 999},
    ],
)
def test_feedback_rejects_invalid_input(
    client,
    app,
    feedback_setup,
    payload,
):
    response = client.post(
        feedback_setup["path"],
        headers=feedback_setup["teacher"]["headers"],
        json=payload,
    )

    assert response.status_code == 400

    with app.app_context():
        assert db.session.scalar(
            db.select(TeacherFeedback.id)
        ) is None


def test_feedback_rejects_non_object_json(client, feedback_setup):
    response = client.post(
        feedback_setup["path"],
        headers=feedback_setup["teacher"]["headers"],
        json=[],
    )

    assert response.status_code == 400


def test_student_keeps_feedback_after_leaving_class(
    client,
    feedback_setup,
):
    setup = feedback_setup
    feedback = send_feedback(client, setup)

    leave_response = client.delete(
        f"/api/classes/{setup['classroom']['id']}/membership",
        headers=setup["student"]["headers"],
    )

    assert leave_response.status_code == 200

    student_list = client.get(
        "/api/feedback/me",
        headers=setup["student"]["headers"],
    )

    assert student_list.status_code == 200
    assert student_list.get_json()["feedback"] == [feedback]

    teacher_list = client.get(
        setup["path"],
        headers=setup["teacher"]["headers"],
    )

    assert teacher_list.status_code == 404

    new_feedback = client.post(
        setup["path"],
        headers=setup["teacher"]["headers"],
        json={"message": "New feedback after leaving."},
    )

    assert new_feedback.status_code == 404


@pytest.mark.parametrize("page", ["0", "-1", "abc", "10001"])
def test_feedback_rejects_invalid_page(client, feedback_setup, page):
    response = client.get(
        f"/api/feedback/me?page={page}",
        headers=feedback_setup["student"]["headers"],
    )

    assert response.status_code == 400


def test_feedback_pagination_returns_newest_first(
    client,
    app,
    feedback_setup,
):
    setup = feedback_setup

    with app.app_context():
        feedback_items = [
            TeacherFeedback(
                classroom_id=setup["classroom"]["id"],
                teacher_id=setup["teacher"]["id"],
                student_id=setup["student"]["id"],
                message=f"Feedback {index}",
            )
            for index in range(21)
        ]

        db.session.add_all(feedback_items)
        db.session.commit()

        expected_ids = sorted(
            [item.id for item in feedback_items],
            reverse=True,
        )

    first_page = client.get(
        "/api/feedback/me?page=1",
        headers=setup["student"]["headers"],
    )

    assert first_page.status_code == 200

    first_data = first_page.get_json()

    assert len(first_data["feedback"]) == 20
    assert first_data["pagination"]["has_more"] is True
    assert [
        item["id"] for item in first_data["feedback"]
    ] == expected_ids[:20]

    second_page = client.get(
        "/api/feedback/me?page=2",
        headers=setup["student"]["headers"],
    )

    assert second_page.status_code == 200

    second_data = second_page.get_json()

    assert len(second_data["feedback"]) == 1
    assert second_data["pagination"]["has_more"] is False
    assert second_data["feedback"][0]["id"] == expected_ids[20]