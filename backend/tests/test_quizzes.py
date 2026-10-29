from extensions import db
from models.quiz_attempt import QuizAttempt
from models.quiz_question import QuizQuestion
from models.topic import Topic
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
import pytest
from flask_jwt_extended import create_access_token

from models.user import User

def authenticated_headers(client):
    with patch(
        "services.email_verification_service.send_email"
    ) as mock_send_email:
        register_response = client.post(
            "/api/auth/register",
            json={
                "name": "Quiz Student",
                "email": "quiz.student@example.com",
                "password": "SecurePass123!",
                "academic_level": "hsc",
            },
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
            "email": "quiz.student@example.com",
            "password": "SecurePass123!",
        },
    )

    assert login_response.status_code == 200

    access_token = login_response.get_json()["access_token"]

    return {
        "Authorization": f"Bearer {access_token}",
    }


def create_quiz_data(app):
    with app.app_context():
        topic = Topic(
            title="Number Systems",
            slug="number-systems",
            description="Learn binary, decimal, and hexadecimal.",
            display_order=1,
            subject="ict",
            academic_level="hsc",
        )

        db.session.add(topic)
        db.session.commit()

        first_question = QuizQuestion(
            topic_id=topic.id,
            question_text="What is binary 10 in decimal?",
            option_a="1",
            option_b="2",
            option_c="8",
            option_d="10",
            correct_option="B",
            explanation="Binary 10 means 2 in decimal.",
            display_order=1,
        )

        second_question = QuizQuestion(
            topic_id=topic.id,
            question_text="What is decimal 15 in binary?",
            option_a="1111",
            option_b="1010",
            option_c="1100",
            option_d="1001",
            correct_option="A",
            explanation="15 in decimal is 1111 in binary.",
            display_order=2,
        )

        db.session.add_all([first_question, second_question])
        db.session.commit()

        return {
            "slug": topic.slug,
            "question_ids": [
                first_question.id,
                second_question.id,
            ],
        }

def test_quiz_route_requires_login(client, app):
    quiz_data = create_quiz_data(app)

    response = client.get(
        f"/api/topics/{quiz_data['slug']}/quiz",
    )

    assert response.status_code == 401


def test_logged_in_user_can_load_topic_quiz(client, app):
    quiz_data = create_quiz_data(app)
    headers = authenticated_headers(client)

    response = client.get(
        f"/api/topics/{quiz_data['slug']}/quiz",
        headers=headers,
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["topic"]["title"] == "Number Systems"
    assert len(data["questions"]) == 2
    assert data["questions"][0]["question_text"] == (
        "What is binary 10 in decimal?"
    )

    # Student quiz load করার সময় answer leak হওয়া যাবে না।
    assert "correct_option" not in data["questions"][0]
    assert "explanation" not in data["questions"][0]


def test_user_can_submit_quiz_and_score_is_calculated(client, app):
    quiz_data = create_quiz_data(app)
    headers = authenticated_headers(client)

    response = client.post(
        f"/api/topics/{quiz_data['slug']}/quiz/submit",
        headers=headers,
        json={
            "answers": [
                {
                    "question_id": quiz_data["question_ids"][0],
                    "selected_option": "B",
                },
                {
                    "question_id": quiz_data["question_ids"][1],
                    "selected_option": "B",
                },
            ],
        },
    )

    assert response.status_code == 201

    data = response.get_json()

    assert data["message"] == "Quiz submitted successfully"
    assert data["attempt"]["topic"] == "Number Systems"
    assert data["attempt"]["score"] == 1
    assert data["attempt"]["total_questions"] == 2

    assert data["results"][0]["is_correct"] is True
    assert data["results"][1]["is_correct"] is False

    with app.app_context():
        saved_attempt = db.session.get(
            QuizAttempt,
            data["attempt"]["id"],
        )

        assert saved_attempt is not None
        assert saved_attempt.score == 1
        assert saved_attempt.total_questions == 2


def test_quiz_submission_requires_all_answers(client, app):
    quiz_data = create_quiz_data(app)
    headers = authenticated_headers(client)

    response = client.post(
        f"/api/topics/{quiz_data['slug']}/quiz/submit",
        headers=headers,
        json={
            "answers": [
                {
                    "question_id": quiz_data["question_ids"][0],
                    "selected_option": "B",
                },
            ],
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == (
        "Submit exactly one answer for every quiz question"
    )



def level_access_headers(app, role="student", academic_level=None):
    with app.app_context():
        user = User(
            name="Quiz Access User",
            email="quiz-access@example.com",
            password_hash="unused-password-hash",
            role=role,
            academic_level=academic_level,
        )
        user.is_email_verified = True

        db.session.add(user)
        db.session.commit()

        token = create_access_token(
            identity=str(user.id),
            additional_claims={
                "token_version": user.token_version,
            },
        )

        return {"Authorization": f"Bearer {token}"}


def request_quiz(client, quiz_data, headers, action):
    path = f"/api/topics/{quiz_data['slug']}/quiz"

    if action == "get":
        return client.get(path, headers=headers)

    return client.post(
        f"{path}/submit",
        headers=headers,
        json={
            "answers": [
                {
                    "question_id": question_id,
                    "selected_option": "B",
                }
                for question_id in quiz_data["question_ids"]
            ],
        },
    )


@pytest.mark.parametrize("academic_level", ["ssc", "hsc"])
@pytest.mark.parametrize("action", ["get", "submit"])
def test_student_can_access_matching_level_quiz(
    app,
    client,
    academic_level,
    action,
):
    quiz_data = create_quiz_data(app)

    with app.app_context():
        topic = db.session.scalar(
            db.select(Topic).where(Topic.slug == quiz_data["slug"])
        )
        assert topic is not None
        topic.academic_level = academic_level
        db.session.commit()

    headers = level_access_headers(
        app,
        academic_level=academic_level,
    )

    response = request_quiz(client, quiz_data, headers, action)

    assert response.status_code == (200 if action == "get" else 201)

    data = response.get_json()

    if action == "get":
        assert len(data["questions"]) == 2

        for question in data["questions"]:
            assert "correct_option" not in question
            assert "explanation" not in question
    else:
        assert data["attempt"]["score"] == 1

    with app.app_context():
        attempts = db.session.scalars(db.select(QuizAttempt)).all()
        assert len(attempts) == (0 if action == "get" else 1)


@pytest.mark.parametrize("student_level", ["ssc", "hsc"])
@pytest.mark.parametrize("action", ["get", "submit"])
def test_student_cannot_access_other_level_quiz(
    app,
    client,
    student_level,
    action,
):
    quiz_data = create_quiz_data(app)
    other_level = "hsc" if student_level == "ssc" else "ssc"

    with app.app_context():
        topic = db.session.scalar(
            db.select(Topic).where(Topic.slug == quiz_data["slug"])
        )
        assert topic is not None
        topic.academic_level = other_level
        db.session.commit()

    headers = level_access_headers(
        app,
        academic_level=student_level,
    )

    response = request_quiz(client, quiz_data, headers, action)

    assert response.status_code == 403

    data = response.get_json()

    assert data["code"] == "TOPIC_LEVEL_MISMATCH"
    assert "questions" not in data
    assert "results" not in data
    assert "attempt" not in data

    with app.app_context():
        assert db.session.scalar(db.select(QuizAttempt)) is None


@pytest.mark.parametrize("action", ["get", "submit"])
def test_student_without_level_cannot_access_quiz(app, client, action):
    quiz_data = create_quiz_data(app)
    headers = level_access_headers(app)

    response = request_quiz(client, quiz_data, headers, action)

    assert response.status_code == 409
    assert response.get_json()["code"] == "ACADEMIC_LEVEL_REQUIRED"

    with app.app_context():
        assert db.session.scalar(db.select(QuizAttempt)) is None


@pytest.mark.parametrize("action", ["get", "submit"])
def test_teacher_cannot_use_student_practice_quiz(app, client, action):
    quiz_data = create_quiz_data(app)
    headers = level_access_headers(app, role="teacher")

    response = request_quiz(client, quiz_data, headers, action)

    assert response.status_code == 403

    with app.app_context():
        assert db.session.scalar(db.select(QuizAttempt)) is None