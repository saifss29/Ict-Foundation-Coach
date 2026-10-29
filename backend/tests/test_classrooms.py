from datetime import datetime, timezone

import pytest

from extensions import db
from models.quiz_attempt import QuizAttempt
from models.topic import Topic
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit


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

    verify_response = client.post(
        "/api/auth/verify-email",
        json={"token": verification_token},
    )

    assert verify_response.status_code == 200

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


def create_class(client, teacher_headers, name="HSC ICT Batch A"):
    response = client.post(
        "/api/classes",
        headers=teacher_headers,
        json={"name": name},
    )

    assert response.status_code == 201

    return response.get_json()["classroom"]


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/classes"),
        ("GET", "/api/classes"),
        ("GET", "/api/classes/1"),
        ("GET", "/api/classes/1/students/1/attempts"),
        ("POST", "/api/classes/join"),
    ],
)
def test_class_routes_require_login(client, method, path):
    response = client.open(
        path,
        method=method,
        json={},
    )

    assert response.status_code == 401


def test_teacher_can_create_class(client):
    headers = login_as(
        client,
        role="teacher",
        email="teacher@example.com",
    )

    response = client.post(
        "/api/classes",
        headers=headers,
        json={"name": "  HSC ICT Batch A  "},
    )

    assert response.status_code == 201

    data = response.get_json()
    classroom = data["classroom"]

    assert data["message"] == "Class created successfully"
    assert classroom["name"] == "HSC ICT Batch A"

    code = classroom["join_code"]

    assert len(code) == 8
    assert all(
        character in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        for character in code
    )

    profile_response = client.get(
        "/api/auth/me",
        headers=headers,
    )

    assert profile_response.status_code == 200
    assert classroom["teacher_id"] == (
        profile_response.get_json()["user"]["id"]
    )

    list_response = client.get("/api/classes", headers=headers)

    assert list_response.status_code == 200
    assert list_response.get_json()["classes"] == [classroom]


def test_student_cannot_create_class(client):
    headers = login_as(
        client,
        role="student",
        email="student@example.com",
    )

    response = client.post(
        "/api/classes",
        headers=headers,
        json={"name": "Unauthorized Class"},
    )

    assert response.status_code == 403

    list_response = client.get("/api/classes", headers=headers)

    assert list_response.get_json()["classes"] == []


def test_teacher_only_sees_own_classes(client):
    first_teacher = login_as(
        client,
        role="teacher",
        email="first-teacher@example.com",
    )
    second_teacher = login_as(
        client,
        role="teacher",
        email="second-teacher@example.com",
    )

    first_class = create_class(client, first_teacher, "First Class")
    second_class = create_class(client, second_teacher, "Second Class")

    first_response = client.get("/api/classes", headers=first_teacher)
    second_response = client.get("/api/classes", headers=second_teacher)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.get_json()["classes"] == [first_class]
    assert second_response.get_json()["classes"] == [second_class]


def test_student_can_join_and_only_sees_joined_classes(client):
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

    joined_class = create_class(client, teacher, "Joined Class")
    create_class(client, teacher, "Other Class")

    response = client.post(
        "/api/classes/join",
        headers=student,
        json={
            "join_code": f"  {joined_class['join_code'].lower()}  ",
        },
    )

    assert response.status_code == 201
    assert response.get_json()["message"] == "Joined class successfully"
    assert response.get_json()["classroom"]["id"] == joined_class["id"]
    assert "join_code" not in response.get_json()["classroom"]

    list_response = client.get("/api/classes", headers=student)

    assert list_response.status_code == 200

    classes = list_response.get_json()["classes"]

    assert len(classes) == 1
    assert classes[0]["id"] == joined_class["id"]
    assert "join_code" not in classes[0]


def test_student_cannot_join_same_class_twice(client):
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

    classroom = create_class(client, teacher)
    payload = {"join_code": classroom["join_code"]}

    first_response = client.post(
        "/api/classes/join",
        headers=student,
        json=payload,
    )
    second_response = client.post(
        "/api/classes/join",
        headers=student,
        json=payload,
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409

    list_response = client.get("/api/classes", headers=student)

    assert len(list_response.get_json()["classes"]) == 1


def test_teacher_cannot_join_class_as_student(client):
    teacher = login_as(
        client,
        role="teacher",
        email="teacher@example.com",
    )

    classroom = create_class(client, teacher)

    response = client.post(
        "/api/classes/join",
        headers=teacher,
        json={"join_code": classroom["join_code"]},
    )

    assert response.status_code == 403


def test_unknown_class_code_is_rejected(client):
    student = login_as(
        client,
        role="student",
        email="student@example.com",
    )

    response = client.post(
        "/api/classes/join",
        headers=student,
        json={"join_code": "ZZZZZZZZ"},
    )

    assert response.status_code == 404

    list_response = client.get("/api/classes", headers=student)

    assert list_response.get_json()["classes"] == []


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": "   "},
        {"name": "A"},
        {"name": "A" * 101},
        {"name": None},
        {"name": 123},
        {"name": "Test Class", "teacher_id": 999},
    ],
)
def test_create_class_rejects_invalid_input(client, payload):
    teacher = login_as(
        client,
        role="teacher",
        email="teacher@example.com",
    )

    response = client.post(
        "/api/classes",
        headers=teacher,
        json=payload,
    )

    assert response.status_code == 400

    list_response = client.get("/api/classes", headers=teacher)

    assert list_response.get_json()["classes"] == []


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"join_code": ""},
        {"join_code": "ABC"},
        {"join_code": "ABCDEFGH9"},
        {"join_code": "ABCD!234"},
        {"join_code": None},
        {"join_code": 123},
    ],
)
def test_join_class_rejects_invalid_input(client, payload):
    student = login_as(
        client,
        role="student",
        email="student@example.com",
    )

    response = client.post(
        "/api/classes/join",
        headers=student,
        json=payload,
    )

    assert response.status_code == 400


@pytest.mark.parametrize(
    ("path", "role"),
    [
        ("/api/classes", "teacher"),
        ("/api/classes/join", "student"),
    ],
)
def test_class_routes_reject_non_object_json(client, path, role):
    headers = login_as(
        client,
        role=role,
        email=f"{role}@example.com",
    )

    response = client.post(
        path,
        headers=headers,
        json=[],
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == (
        "Request body must be a JSON object"
    )


def test_student_cannot_view_class_analytics(client):
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

    classroom = create_class(client, teacher)

    response = client.get(
        f"/api/classes/{classroom['id']}",
        headers=student,
    )

    assert response.status_code == 403
    assert response.get_json()["error"] == (
        "Only teachers can view class analytics"
    )


def test_teacher_cannot_view_another_teachers_class_analytics(client):
    first_teacher = login_as(
        client,
        role="teacher",
        email="first-teacher@example.com",
    )
    second_teacher = login_as(
        client,
        role="teacher",
        email="second-teacher@example.com",
    )

    classroom = create_class(client, first_teacher)

    response = client.get(
        f"/api/classes/{classroom['id']}",
        headers=second_teacher,
    )

    assert response.status_code == 403
    assert response.get_json()["error"] == "You do not own this class"


def test_teacher_can_view_student_class_analytics(client):
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

    classroom = create_class(client, teacher)

    join_response = client.post(
        "/api/classes/join",
        headers=student,
        json={"join_code": classroom["join_code"]},
    )

    assert join_response.status_code == 201

    student_profile_response = client.get(
        "/api/auth/me",
        headers=student,
    )

    assert student_profile_response.status_code == 200

    student_id = student_profile_response.get_json()["user"]["id"]

    topic = Topic(
        title="Number System Analytics Topic",
        slug="number-system-analytics",
        description="Test topic for classroom analytics.",
        display_order=1,
    )

    db.session.add(topic)
    db.session.commit()

    attempt = QuizAttempt(
        user_id=student_id,
        topic_id=topic.id,
        score=2,
        total_questions=5,
    )

    db.session.add(attempt)
    db.session.commit()

    response = client.get(
        f"/api/classes/{classroom['id']}",
        headers=teacher,
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["classroom"]["id"] == classroom["id"]
    assert data["classroom"]["join_code"] == classroom["join_code"]

    assert data["summary"] == {
        "student_count": 1,
        "students_started_learning": 1,
        "total_quiz_attempts": 1,
        "class_average_latest_percentage": 40,
    }

    assert len(data["students"]) == 1

    analytics_student = data["students"][0]

    assert analytics_student["id"] == student_id
    assert analytics_student["email"] == "student@example.com"
    assert analytics_student["total_attempts"] == 1
    assert analytics_student["latest_score"] == 2
    assert analytics_student["latest_total_questions"] == 5
    assert analytics_student["latest_percentage"] == 40
    assert analytics_student["last_quiz_at"] is not None

    assert analytics_student["weakest_topic"] == {
        "title": "Number System Analytics Topic",
        "slug": "number-system-analytics",
        "percentage": 40,
    }


def test_student_cannot_view_attempt_history(client):
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

    classroom = create_class(client, teacher)

    profile_response = client.get(
        "/api/auth/me",
        headers=student,
    )

    student_id = profile_response.get_json()["user"]["id"]

    response = client.get(
        f"/api/classes/{classroom['id']}/students/{student_id}/attempts",
        headers=student,
    )

    assert response.status_code == 403
    assert response.get_json()["error"] == (
        "Only teachers can view student attempt history"
    )


def test_teacher_cannot_view_non_member_attempt_history(client):
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

    classroom = create_class(client, teacher)

    profile_response = client.get(
        "/api/auth/me",
        headers=student,
    )

    student_id = profile_response.get_json()["user"]["id"]

    response = client.get(
        f"/api/classes/{classroom['id']}/students/{student_id}/attempts",
        headers=teacher,
    )

    assert response.status_code == 404
    assert response.get_json()["error"] == (
        "Student is not a member of this class"
    )


def test_teacher_can_view_joined_student_attempt_history(client):
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

    classroom = create_class(client, teacher)

    join_response = client.post(
        "/api/classes/join",
        headers=student,
        json={"join_code": classroom["join_code"]},
    )

    assert join_response.status_code == 201

    profile_response = client.get(
        "/api/auth/me",
        headers=student,
    )

    student_id = profile_response.get_json()["user"]["id"]

    first_topic = Topic(
        title="First History Topic",
        slug="first-history-topic",
        description="First history test topic.",
        display_order=1,
    )
    second_topic = Topic(
        title="Second History Topic",
        slug="second-history-topic",
        description="Second history test topic.",
        display_order=2,
    )

    db.session.add_all([first_topic, second_topic])
    db.session.commit()

    older_attempt = QuizAttempt(
        user_id=student_id,
        topic_id=first_topic.id,
        score=1,
        total_questions=5,
    )
    older_attempt.completed_at = datetime(
        2026,
        1,
        1,
        tzinfo=timezone.utc,
    )

    latest_attempt = QuizAttempt(
        user_id=student_id,
        topic_id=second_topic.id,
        score=4,
        total_questions=5,
    )
    latest_attempt.completed_at = datetime(
        2026,
        1,
        2,
        tzinfo=timezone.utc,
    )

    db.session.add_all([older_attempt, latest_attempt])
    db.session.commit()

    response = client.get(
        f"/api/classes/{classroom['id']}/students/{student_id}/attempts",
        headers=teacher,
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["classroom"] == {
        "id": classroom["id"],
        "name": classroom["name"],
    }

    assert data["student"]["id"] == student_id
    assert data["student"]["name"] == "Test Student"
    assert data["student"]["email"] == "student@example.com"
    assert data["student"]["joined_at"]

    assert len(data["attempts"]) == 2

    assert data["attempts"][0] == {
        "id": latest_attempt.id,
        "topic": "Second History Topic",
        "topic_slug": "second-history-topic",
        "score": 4,
        "total_questions": 5,
        "percentage": 80,
        "completed_at": "2026-01-02T00:00:00",
    }

    assert data["attempts"][1] == {
        "id": older_attempt.id,
        "topic": "First History Topic",
        "topic_slug": "first-history-topic",
        "score": 1,
        "total_questions": 5,
        "percentage": 20,
        "completed_at": "2026-01-01T00:00:00",
    }