from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from extensions import db
from models.quiz_attempt import QuizAttempt
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
    ) as mock_send_email:
        registration = client.post(
            "/api/auth/register",
            json=registration_data,
        )

        assert registration.status_code == 201
        mock_send_email.assert_called_once()

        email_body = mock_send_email.call_args.kwargs["body"]

    verification_link = next(
        line.strip()
        for line in email_body.splitlines()
        if line.strip().startswith(
            "http://localhost:5173/verify-email?"
        )
    )

    token = parse_qs(
        urlsplit(verification_link).query
    )["token"][0]

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
        "user_id": data["user"]["id"],
        "headers": {
            "Authorization": f"Bearer {data['access_token']}",
        },
    }

def create_joined_class(client):
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

    return teacher, student, classroom, joined.get_json()["classroom"]


def test_leave_requires_login(client):
    response = client.delete("/api/classes/1/membership")

    assert response.status_code == 401


def test_join_and_list_show_teacher_name(client):
    teacher, student, classroom, joined_class = create_joined_class(client)

    assert classroom["teacher_name"] == "Test Teacher"
    assert joined_class["teacher_name"] == "Test Teacher"
    assert "join_code" not in joined_class

    response = client.get(
        "/api/classes",
        headers=student["headers"],
    )

    assert response.status_code == 200

    classes = response.get_json()["classes"]

    assert len(classes) == 1
    assert classes[0]["id"] == classroom["id"]
    assert classes[0]["teacher_name"] == "Test Teacher"
    assert "join_code" not in classes[0]


def test_leave_preserves_progress_and_removes_teacher_access(client, app):
    teacher, student, classroom, joined_class = create_joined_class(client)

    with app.app_context():
        topic = Topic(
            title="Membership Test Topic",
            slug="membership-test-topic",
            description="Test progress after leaving a class.",
            display_order=1,
        )

        db.session.add(topic)
        db.session.flush()

        attempt = QuizAttempt(
            user_id=student["user_id"],
            topic_id=topic.id,
            score=2,
            total_questions=5,
        )

        db.session.add(attempt)
        db.session.commit()

        attempt_id = attempt.id

    response = client.delete(
        f"/api/classes/{classroom['id']}/membership",
        headers=student["headers"],
    )

    assert response.status_code == 200
    assert response.get_json()["message"] == "Left class successfully"

    classes_response = client.get(
        "/api/classes",
        headers=student["headers"],
    )

    assert classes_response.status_code == 200
    assert classes_response.get_json()["classes"] == []

    with app.app_context():
        saved_attempt = db.session.get(QuizAttempt, attempt_id)

        assert saved_attempt is not None
        assert saved_attempt.score == 2

    progress_response = client.get(
        "/api/progress",
        headers=student["headers"],
    )

    assert progress_response.status_code == 200

    saved_topic = next(
        topic
        for topic in progress_response.get_json()["topics"]
        if topic["title"] == "Membership Test Topic"
    )

    assert saved_topic["attempt_count"] == 1
    assert saved_topic["latest_score"] == 2

    analytics_response = client.get(
        f"/api/classes/{classroom['id']}",
        headers=teacher["headers"],
    )

    assert analytics_response.status_code == 200
    assert analytics_response.get_json()["students"] == []

    history_response = client.get(
        (
            f"/api/classes/{classroom['id']}"
            f"/students/{student['user_id']}/attempts"
        ),
        headers=teacher["headers"],
    )

    assert history_response.status_code == 404
    assert history_response.get_json()["error"] == (
        "Student is not a member of this class"
    )

    repeated_leave = client.delete(
        f"/api/classes/{classroom['id']}/membership",
        headers=student["headers"],
    )

    assert repeated_leave.status_code == 404

    rejoined = client.post(
        "/api/classes/join",
        headers=student["headers"],
        json={"join_code": classroom["join_code"]},
    )

    assert rejoined.status_code == 201


def test_student_cannot_remove_another_students_membership(client):
    teacher, student, classroom, joined_class = create_joined_class(client)

    outsider = login_as(
        client,
        role="student",
        email="outsider@example.com",
    )

    response = client.delete(
        f"/api/classes/{classroom['id']}/membership",
        headers=outsider["headers"],
    )

    assert response.status_code == 404

    classes_response = client.get(
        "/api/classes",
        headers=student["headers"],
    )

    assert classes_response.status_code == 200

    classes = classes_response.get_json()["classes"]

    assert len(classes) == 1
    assert classes[0]["id"] == classroom["id"]


def test_teacher_cannot_leave_class(client):
    teacher, student, classroom, joined_class = create_joined_class(client)

    response = client.delete(
        f"/api/classes/{classroom['id']}/membership",
        headers=teacher["headers"],
    )

    assert response.status_code == 403

    classes_response = client.get(
        "/api/classes",
        headers=student["headers"],
    )

    assert len(classes_response.get_json()["classes"]) == 1


def test_student_cannot_leave_unknown_class(client):
    student = login_as(
        client,
        role="student",
        email="student@example.com",
    )

    response = client.delete(
        "/api/classes/999999/membership",
        headers=student["headers"],
    )

    assert response.status_code == 404