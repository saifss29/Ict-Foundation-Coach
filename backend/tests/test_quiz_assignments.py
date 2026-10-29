from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from models.class_membership import ClassMembership
from models.classroom import Classroom
from models.notification import Notification
from models.quiz_assignment import QuizAssignment
from models.quiz_assignment_recipient import QuizAssignmentRecipient
from models.teacher_quiz import TeacherQuiz
from models.topic import Topic
from models.user import User
from models.quiz_assignment_attempt import QuizAssignmentAttempt
from models.quiz_attempt import QuizAttempt


def create_assignment_user(client, app, role, email):
    registration_data = {
        "name": f"Assignment {role.title()}",
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
    assert response.status_code == 201
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
            )
        },
    }

@pytest.fixture()
def assignment_setup(client, app):
    teacher = create_assignment_user(
        client, app, "teacher", "assign-owner@example.com"
    )
    other_teacher = create_assignment_user(
        client, app, "teacher", "assign-other@example.com"
    )
    students = [
        create_assignment_user(
            client, app, "student", f"assign-student-{index}@example.com"
        )
        for index in range(3)
    ]

    with app.app_context():
        classroom = Classroom(
            name="HSC Assignment Class",
            teacher_id=teacher["id"],
            join_code="ASSIGN01",
        )
        other_class = Classroom(
            name="Other Teacher Class",
            teacher_id=other_teacher["id"],
            join_code="ASSIGN02",
        )
        topic = Topic(
            title="Number Systems",
            slug="number-systems",
            description="Verified ICT practice topic.",
            display_order=1,
        )
        db.session.add_all([classroom, other_class, topic])
        db.session.flush()

        quiz = TeacherQuiz(
            teacher_id=teacher["id"],
            topic_id=topic.id,
            title="Published Assignment Quiz",
            response_language="english",
            questions=[
                {
                    "id": str(index),
                    "question_text": f"Question {index}",
                    "option_a": "2",
                    "option_b": "8",
                    "option_c": "10",
                    "option_d": "16",
                    "correct_option": "A",
                    "explanation": "Binary uses base 2.",
                }
                for index in range(1, 6)
            ],
        )
        quiz.status = "published"
        quiz.published_at = datetime.now(timezone.utc)
        db.session.add(quiz)

        # First two students are enrolled; the third is an outsider.
        for student in students[:2]:
            db.session.add(
                ClassMembership(
                    classroom_id=classroom.id,
                    student_id=student["id"],
                )
            )

        db.session.commit()

        return {
            "teacher": teacher,
            "other_teacher": other_teacher,
            "students": students,
            "classroom_id": classroom.id,
            "other_classroom_id": other_class.id,
            "quiz_id": quiz.id,
        }


def assignment_request(setup):
    now = datetime.now(timezone.utc)

    return {
        "quiz_id": setup["quiz_id"],
        "classroom_id": setup["classroom_id"],
        "audience": "all",
        "available_at": now.isoformat(),
        "deadline_at": (now + timedelta(days=1)).isoformat(),
        "time_limit_minutes": 30,
        "max_attempts": 2,
        "review_at": (now + timedelta(days=1)).isoformat(),
    }


def assert_no_assignment_records(app):
    with app.app_context():
        for model in (
            QuizAssignment,
            QuizAssignmentRecipient,
            Notification,
        ):
            assert db.session.scalar(
                db.select(db.func.count()).select_from(model)
            ) == 0


def test_assignment_requires_login(client):
    response = client.post("/api/quiz-assignments", json={})
    assert response.status_code == 401


def test_student_cannot_assign_quiz(client, app, assignment_setup):
    setup = assignment_setup
    response = client.post(
        "/api/quiz-assignments",
        headers=setup["students"][0]["headers"],
        json=assignment_request(setup),
    )

    assert response.status_code == 403
    assert_no_assignment_records(app)


@pytest.mark.parametrize("audience", ["all", "selected"])
def test_teacher_assigns_only_intended_students(
    client, app, assignment_setup, audience
):
    setup = assignment_setup
    payload = assignment_request(setup)
    payload["audience"] = audience

    expected_ids = {student["id"] for student in setup["students"][:2]}

    if audience == "selected":
        expected_ids = {setup["students"][1]["id"]}
        payload["student_ids"] = list(expected_ids)

    response = client.post(
        "/api/quiz-assignments",
        headers=setup["teacher"]["headers"],
        json=payload,
    )

    assert response.status_code == 201
    assignment = response.get_json()["assignment"]
    assert assignment["recipient_count"] == len(expected_ids)
    assert assignment["quiz_id"] == setup["quiz_id"]
    assert assignment["classroom_id"] == setup["classroom_id"]
    assert assignment["time_limit_minutes"] == 30
    assert assignment["max_attempts"] == 2
    assert "questions" not in assignment

    with app.app_context():
        saved = db.session.get(QuizAssignment, assignment["id"])
        assert saved is not None
        assert saved.audience == audience

        recipients = db.session.scalars(
            db.select(QuizAssignmentRecipient).where(
                QuizAssignmentRecipient.assignment_id == assignment["id"]
            )
        ).all()
        assert {item.student_id for item in recipients} == expected_ids

        notifications = db.session.scalars(
            db.select(Notification)
        ).all()
        assert {item.user_id for item in notifications} == expected_ids
        assert len(notifications) == len(expected_ids)
        assert all(
            item.notification_type == "quiz_assignment"
            and item.read_at is None
            for item in notifications
        )


@pytest.mark.parametrize(
    "invalid_case",
    [
        "other-class",
        "missing-class",
        "other-quiz-owner",
        "missing-quiz",
        "draft-quiz",
        "past-deadline",
        "outsider-student",
        "mixed-students",
        "empty-class",
    ],
)
def test_assignment_rejects_invalid_access_or_state(
    client, app, assignment_setup, invalid_case
):
    setup = assignment_setup
    payload = assignment_request(setup)
    expected_status = 400

    if invalid_case == "other-class":
        payload["classroom_id"] = setup["other_classroom_id"]
        expected_status = 404
    elif invalid_case == "missing-class":
        payload["classroom_id"] = 999999
        expected_status = 404
    elif invalid_case == "missing-quiz":
        payload["quiz_id"] = str(uuid4())
        expected_status = 404
    elif invalid_case in {"other-quiz-owner", "draft-quiz"}:
        with app.app_context():
            quiz = db.session.get(TeacherQuiz, setup["quiz_id"])
            assert quiz is not None

            if invalid_case == "other-quiz-owner":
                quiz.teacher_id = setup["other_teacher"]["id"]
                expected_status = 404
            else:
                quiz.status = "draft"
                quiz.published_at = None
                expected_status = 409

            db.session.commit()
    elif invalid_case == "past-deadline":
        now = datetime.now(timezone.utc)
        payload["available_at"] = (now - timedelta(days=2)).isoformat()
        payload["deadline_at"] = (now - timedelta(days=1)).isoformat()
        payload["review_at"] = payload["deadline_at"]
    elif invalid_case in {"outsider-student", "mixed-students"}:
        payload["audience"] = "selected"
        payload["student_ids"] = [setup["students"][2]["id"]]

        if invalid_case == "mixed-students":
            payload["student_ids"].append(setup["students"][0]["id"])
    elif invalid_case == "empty-class":
        with app.app_context():
            db.session.execute(
                db.delete(ClassMembership).where(
                    ClassMembership.classroom_id == setup["classroom_id"]
                )
            )
            db.session.commit()

    response = client.post(
        "/api/quiz-assignments",
        headers=setup["teacher"]["headers"],
        json=payload,
    )

    assert response.status_code == expected_status
    assert_no_assignment_records(app)


@pytest.mark.parametrize("payload", [None, [], {}, {"teacher_id": 999}])
def test_assignment_rejects_invalid_request(
    client, app, assignment_setup, payload
):
    response = client.post(
        "/api/quiz-assignments",
        headers=assignment_setup["teacher"]["headers"],
        json=payload,
    )

    assert response.status_code == 400
    assert_no_assignment_records(app)


def test_assignment_failure_rolls_back_and_retry_succeeds(
    client, app, assignment_setup, monkeypatch
):
    setup = assignment_setup
    payload = assignment_request(setup)

    with monkeypatch.context() as patch:
        patch.setattr(
            db.session,
            "commit",
            Mock(side_effect=SQLAlchemyError("Test commit failure")),
        )

        response = client.post(
            "/api/quiz-assignments",
            headers=setup["teacher"]["headers"],
            json=payload,
        )

    assert response.status_code == 500
    assert_no_assignment_records(app)

    response = client.post(
        "/api/quiz-assignments",
        headers=setup["teacher"]["headers"],
        json=payload,
    )

    assert response.status_code == 201

    with app.app_context():
        assert db.session.scalar(
            db.select(db.func.count()).select_from(QuizAssignment)
        ) == 1
        assert db.session.scalar(
            db.select(db.func.count()).select_from(QuizAssignmentRecipient)
        ) == 2
        assert db.session.scalar(
            db.select(db.func.count()).select_from(Notification)
        ) == 2

def create_assignment_for_list_test(client, setup, *, student_ids=None):
    payload = assignment_request(setup)

    if student_ids is not None:
        payload["audience"] = "selected"
        payload["student_ids"] = student_ids

    response = client.post(
        "/api/quiz-assignments",
        headers=setup["teacher"]["headers"],
        json=payload,
    )

    assert response.status_code == 201
    return response.get_json()["assignment"]["id"]


def test_assignment_list_requires_login(client):
    response = client.get("/api/quiz-assignments")

    assert response.status_code == 401


@pytest.mark.parametrize("role", ["teacher", "student"])
def test_assignment_list_returns_empty_list(
    client, assignment_setup, role
):
    setup = assignment_setup
    user = (
        setup["teacher"]
        if role == "teacher"
        else setup["students"][0]
    )

    response = client.get(
        "/api/quiz-assignments",
        headers=user["headers"],
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "assignments": [],
        "pagination": {
            "page": 1,
            "page_size": 20,
            "has_more": False,
        },
    }


def test_teacher_list_returns_own_assignment_summary(
    client, assignment_setup
):
    setup = assignment_setup
    assignment_id = create_assignment_for_list_test(client, setup)

    response = client.get(
        "/api/quiz-assignments",
        headers=setup["teacher"]["headers"],
    )

    assert response.status_code == 200
    items = response.get_json()["assignments"]
    assert len(items) == 1

    item = items[0]
    assert item["id"] == assignment_id
    assert item["quiz_id"] == setup["quiz_id"]
    assert item["classroom_id"] == setup["classroom_id"]
    assert item["quiz_title"] == "Published Assignment Quiz"
    assert item["classroom_name"] == "HSC Assignment Class"
    assert item["teacher_name"] == "Assignment Teacher"
    assert item["question_count"] == 5
    assert item["response_language"] == "english"
    assert item["recipient_count"] == 2

    for field in ("questions", "correct_option", "explanation"):
        assert field not in item


def test_other_teacher_cannot_list_assignment(
    client, assignment_setup
):
    setup = assignment_setup
    create_assignment_for_list_test(client, setup)

    response = client.get(
        "/api/quiz-assignments",
        headers=setup["other_teacher"]["headers"],
    )

    assert response.status_code == 200
    assert response.get_json()["assignments"] == []


@pytest.mark.parametrize(
    "student_index, expected_visible",
    [(0, False), (1, True), (2, False)],
)
def test_student_list_only_includes_received_assignments(
    client, assignment_setup, student_index, expected_visible
):
    setup = assignment_setup
    assignment_id = create_assignment_for_list_test(
        client,
        setup,
        student_ids=[setup["students"][1]["id"]],
    )

    response = client.get(
        "/api/quiz-assignments",
        headers=setup["students"][student_index]["headers"],
    )

    assert response.status_code == 200
    items = response.get_json()["assignments"]

    if not expected_visible:
        assert items == []
        return

    assert len(items) == 1
    assert items[0]["id"] == assignment_id
    assert items[0]["quiz_title"] == "Published Assignment Quiz"

    for field in (
        "questions",
        "correct_option",
        "explanation",
        "recipient_count",
        "student_ids",
    ):
        assert field not in items[0]

    # Ensure answer content is absent from the whole response.
    body = response.get_data(as_text=True)
    assert "correct_option" not in body
    assert "Binary uses base 2." not in body


def test_later_class_join_does_not_grant_old_assignment(
    client, app, assignment_setup
):
    setup = assignment_setup
    create_assignment_for_list_test(client, setup)

    with app.app_context():
        db.session.add(
            ClassMembership(
                classroom_id=setup["classroom_id"],
                student_id=setup["students"][2]["id"],
            )
        )
        db.session.commit()

    response = client.get(
        "/api/quiz-assignments",
        headers=setup["students"][2]["headers"],
    )

    assert response.status_code == 200
    assert response.get_json()["assignments"] == []


@pytest.mark.parametrize("page", ["0", "-1", "abc", "10001"])
def test_assignment_list_rejects_invalid_page(
    client, assignment_setup, page
):
    response = client.get(
        f"/api/quiz-assignments?page={page}",
        headers=assignment_setup["teacher"]["headers"],
    )

    assert response.status_code == 400


@pytest.mark.parametrize("role", ["teacher", "student"])
def test_assignment_list_pagination(
    client, app, assignment_setup, role
):
    setup = assignment_setup
    now = datetime.now(timezone.utc)
    expected_ids = []

    # Insert records directly: this test checks listing, not creation.
    with app.app_context():
        for index in range(21):
            assignment = QuizAssignment(
                quiz_id=setup["quiz_id"],
                classroom_id=setup["classroom_id"],
                audience="selected",
                available_at=now,
                deadline_at=now + timedelta(days=1),
                time_limit_minutes=30,
                max_attempts=1,
                review_at=now + timedelta(days=1),
            )
            assignment.created_at = now + timedelta(seconds=index)
            db.session.add(assignment)
            db.session.flush()

            db.session.add(
                QuizAssignmentRecipient(
                    assignment_id=assignment.id,
                    student_id=setup["students"][0]["id"],
                )
            )
            expected_ids.append(assignment.id)

        db.session.commit()

    user = (
        setup["teacher"]
        if role == "teacher"
        else setup["students"][0]
    )
    expected_ids.reverse()

    first = client.get(
        "/api/quiz-assignments?page=1",
        headers=user["headers"],
    )
    second = client.get(
        "/api/quiz-assignments?page=2",
        headers=user["headers"],
    )
    third = client.get(
        "/api/quiz-assignments?page=3",
        headers=user["headers"],
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 200

    first_data = first.get_json()
    second_data = second.get_json()
    third_data = third.get_json()

    assert [
        item["id"] for item in first_data["assignments"]
    ] == expected_ids[:20]
    assert first_data["pagination"] == {
        "page": 1,
        "page_size": 20,
        "has_more": True,
    }

    assert [
        item["id"] for item in second_data["assignments"]
    ] == expected_ids[20:]
    assert second_data["pagination"] == {
        "page": 2,
        "page_size": 20,
        "has_more": False,
    }

    assert third_data["assignments"] == []
    assert third_data["pagination"]["has_more"] is False


def start_assignment(client, setup, assignment_id, student_index=0):
    return client.post(
        f"/api/quiz-assignments/{assignment_id}/start",
        headers=setup["students"][student_index]["headers"],
        json={},
    )


def test_assignment_start_requires_login(client):
    response = client.post(
        "/api/quiz-assignments/unknown/start",
        json={},
    )
    assert response.status_code == 401


def test_teacher_cannot_start_assignment(client, assignment_setup):
    response = client.post(
        "/api/quiz-assignments/unknown/start",
        headers=assignment_setup["teacher"]["headers"],
        json={},
    )
    assert response.status_code == 403


def test_student_starts_and_resumes_same_attempt(
    client, app, assignment_setup
):
    setup = assignment_setup
    assignment_id = create_assignment_for_list_test(client, setup)

    first = start_assignment(client, setup, assignment_id)
    assert first.status_code == 201
    attempt = first.get_json()["attempt"]

    assert attempt["assignment_id"] == assignment_id
    assert attempt["attempt_number"] == 1
    assert attempt["total_questions"] == 5
    assert attempt["answers"] == {}
    assert len(attempt["questions"]) == 5

    expected_fields = {
        "id",
        "question_text",
        "option_a",
        "option_b",
        "option_c",
        "option_d",
    }
    assert all(
        set(question) == expected_fields
        for question in attempt["questions"]
    )
    assert "correct_option" not in first.get_data(as_text=True)
    assert "explanation" not in first.get_data(as_text=True)

    started = datetime.fromisoformat(attempt["started_at"])
    expires = datetime.fromisoformat(attempt["expires_at"])
    assert expires - started == timedelta(minutes=30)

    resumed = start_assignment(client, setup, assignment_id)
    assert resumed.status_code == 200
    resumed_attempt = resumed.get_json()["attempt"]

    assert resumed_attempt["id"] == attempt["id"]
    assert resumed_attempt["started_at"] == attempt["started_at"]
    assert resumed_attempt["expires_at"] == attempt["expires_at"]

    with app.app_context():
        assert db.session.scalar(
            db.select(db.func.count()).select_from(
                QuizAssignmentAttempt
            )
        ) == 1


@pytest.mark.parametrize("case", ["missing", "not-selected", "outsider"])
def test_assignment_start_rejects_inaccessible_assignment(
    client, assignment_setup, case
):
    setup = assignment_setup
    assignment_id = create_assignment_for_list_test(
        client,
        setup,
        student_ids=[setup["students"][1]["id"]],
    )

    if case == "missing":
        assignment_id = str(uuid4())

    student_index = 2 if case == "outsider" else 0
    response = start_assignment(
        client, setup, assignment_id, student_index
    )
    assert response.status_code == 404


@pytest.mark.parametrize("case", ["upcoming", "closed", "draft", "invalid"])
def test_assignment_start_rejects_unavailable_quiz(
    client, app, assignment_setup, case
):
    setup = assignment_setup
    assignment_id = create_assignment_for_list_test(client, setup)

    with app.app_context():
        assignment = db.session.get(QuizAssignment, assignment_id)
        quiz = db.session.get(TeacherQuiz, setup["quiz_id"])
        assert assignment is not None
        assert quiz is not None
        now = datetime.now(timezone.utc)

        if case == "upcoming":
            assignment.available_at = now + timedelta(hours=1)
            assignment.deadline_at = now + timedelta(hours=2)
            assignment.review_at = assignment.deadline_at
        elif case == "closed":
            assignment.available_at = now - timedelta(hours=2)
            assignment.deadline_at = now - timedelta(hours=1)
            assignment.review_at = assignment.deadline_at
        elif case == "draft":
            quiz.status = "draft"
        else:
            quiz.questions = []

        db.session.commit()

    response = start_assignment(client, setup, assignment_id)
    assert response.status_code == 409

    with app.app_context():
        assert db.session.scalar(
            db.select(db.func.count()).select_from(
                QuizAssignmentAttempt
            )
        ) == 0


@pytest.mark.parametrize("payload", [None, [], {"score": 5}])
def test_assignment_start_rejects_invalid_body(
    client, assignment_setup, payload
):
    response = client.post(
        "/api/quiz-assignments/unknown/start",
        headers=assignment_setup["students"][0]["headers"],
        json=payload,
    )
    assert response.status_code == 400


def test_assignment_start_caps_expiry_at_deadline(
    client, app, assignment_setup
):
    setup = assignment_setup
    assignment_id = create_assignment_for_list_test(client, setup)
    deadline = datetime.now(timezone.utc) + timedelta(minutes=5)

    with app.app_context():
        assignment = db.session.get(QuizAssignment, assignment_id)
        assert assignment is not None
        assignment.deadline_at = deadline
        assignment.review_at = deadline
        db.session.commit()

    response = start_assignment(client, setup, assignment_id)
    assert response.status_code == 201
    attempt = response.get_json()["attempt"]

    assert datetime.fromisoformat(attempt["expires_at"]) == deadline


def test_expired_attempt_consumes_limit(
    client, app, assignment_setup
):
    setup = assignment_setup
    assignment_id = create_assignment_for_list_test(client, setup)

    with app.app_context():
        assignment = db.session.get(QuizAssignment, assignment_id)
        assert assignment is not None
        assignment.max_attempts = 2

        now = datetime.now(timezone.utc)
        db.session.add(
            QuizAssignmentAttempt(
                assignment_id=assignment_id,
                student_id=setup["students"][0]["id"],
                attempt_number=1,
                started_at=now - timedelta(minutes=40),
                expires_at=now - timedelta(minutes=10),
                total_questions=5,
            )
        )
        db.session.commit()

    response = start_assignment(client, setup, assignment_id)
    assert response.status_code == 201
    assert response.get_json()["attempt"]["attempt_number"] == 2

    with app.app_context():
        latest = db.session.get(
            QuizAssignmentAttempt,
            response.get_json()["attempt"]["id"],
        )
        assert latest is not None
        latest.started_at = now - timedelta(minutes=5)
        latest.expires_at = now - timedelta(minutes=1)
        db.session.commit()

    response = start_assignment(client, setup, assignment_id)
    assert response.status_code == 409

    with app.app_context():
        assert db.session.scalar(
            db.select(db.func.count()).select_from(
                QuizAssignmentAttempt
            )
        ) == 2


def test_assignment_start_failure_rolls_back(
    client, app, assignment_setup, monkeypatch
):
    setup = assignment_setup
    assignment_id = create_assignment_for_list_test(client, setup)

    with monkeypatch.context() as patch:
        patch.setattr(
            db.session,
            "commit",
            Mock(side_effect=SQLAlchemyError("Test commit failure")),
        )
        response = start_assignment(client, setup, assignment_id)

    assert response.status_code == 500

    with app.app_context():
        assert db.session.scalar(
            db.select(db.func.count()).select_from(
                QuizAssignmentAttempt
            )
        ) == 0

    retry = start_assignment(client, setup, assignment_id)
    assert retry.status_code == 201
    assert retry.get_json()["attempt"]["attempt_number"] == 1


def prepare_answer_attempt(client, setup):
    assignment_id = create_assignment_for_list_test(client, setup)
    response = start_assignment(client, setup, assignment_id)
    assert response.status_code == 201

    return assignment_id, response.get_json()["attempt"]["id"]


def send_attempt_answers(
    client,
    setup,
    assignment_id,
    attempt_id,
    *,
    submit=False,
    answers=None,
    student_index=0,
):
    suffix = "submit" if submit else "answers"
    method = "POST" if submit else "PATCH"

    return client.open(
        f"/api/quiz-assignments/{assignment_id}"
        f"/attempts/{attempt_id}/{suffix}",
        method=method,
        headers=setup["students"][student_index]["headers"],
        json={"answers": answers if answers is not None else {}},
    )


@pytest.mark.parametrize("submit", [False, True])
def test_assignment_answers_require_login(client, submit):
    suffix = "submit" if submit else "answers"
    response = client.open(
        f"/api/quiz-assignments/unknown/attempts/unknown/{suffix}",
        method="POST" if submit else "PATCH",
        json={"answers": {}},
    )
    assert response.status_code == 401


@pytest.mark.parametrize("submit", [False, True])
def test_teacher_cannot_answer_assignment(
    client, assignment_setup, submit
):
    suffix = "submit" if submit else "answers"
    response = client.open(
        f"/api/quiz-assignments/unknown/attempts/unknown/{suffix}",
        method="POST" if submit else "PATCH",
        headers=assignment_setup["teacher"]["headers"],
        json={"answers": {}},
    )
    assert response.status_code == 403


def test_assignment_answers_save_replace_and_resume(
    client, app, assignment_setup
):
    setup = assignment_setup
    assignment_id, attempt_id = prepare_answer_attempt(client, setup)

    first = send_attempt_answers(
        client, setup, assignment_id, attempt_id,
        answers={"1": "A", "2": "B"},
    )
    assert first.status_code == 200

    second = send_attempt_answers(
        client, setup, assignment_id, attempt_id,
        answers={"1": "C"},
    )
    assert second.status_code == 200
    assert second.get_json()["attempt"]["answers"] == {"1": "C"}

    resumed = start_assignment(client, setup, assignment_id)
    assert resumed.status_code == 200
    assert resumed.get_json()["attempt"]["answers"] == {"1": "C"}

    with app.app_context():
        saved = db.session.get(QuizAssignmentAttempt, attempt_id)
        assert saved is not None
        assert saved.answers == {"1": "C"}
        assert saved.submitted_at is None
        assert db.session.scalar(
            db.select(db.func.count()).select_from(QuizAttempt)
        ) == 0


def test_assignment_submit_grades_and_is_idempotent(
    client, app, assignment_setup
):
    setup = assignment_setup
    assignment_id, attempt_id = prepare_answer_attempt(client, setup)

    response = send_attempt_answers(
        client, setup, assignment_id, attempt_id,
        submit=True,
        answers={"1": "A", "2": "A", "3": "B"},
    )
    assert response.status_code == 200
    result = response.get_json()["result"]
    assert result["score"] == 2
    assert result["total_questions"] == 5

    body = response.get_data(as_text=True)
    assert "correct_option" not in body
    assert "explanation" not in body
    assert "questions" not in result

    retry = send_attempt_answers(
        client, setup, assignment_id, attempt_id,
        submit=True,
        answers={"1": "D"},
    )
    assert retry.status_code == 200
    assert retry.get_json()["result"] == result

    edit = send_attempt_answers(
        client, setup, assignment_id, attempt_id,
        answers={"1": "D"},
    )
    assert edit.status_code == 409

    with app.app_context():
        saved = db.session.get(QuizAssignmentAttempt, attempt_id)
        assert saved is not None
        assert saved.answers == {"1": "A", "2": "A", "3": "B"}
        progress = db.session.get(QuizAttempt, saved.quiz_attempt_id)
        assert progress is not None
        assert progress.user_id == setup["students"][0]["id"]
        assert progress.topic_id is not None
        assert progress.score == 2
        assert progress.total_questions == 5
        assert db.session.scalar(
            db.select(db.func.count()).select_from(QuizAttempt)
        ) == 1


@pytest.mark.parametrize("submit", [False, True])
@pytest.mark.parametrize("student_index", [1, 2])
def test_student_cannot_answer_another_students_attempt(
    client, assignment_setup, submit, student_index
):
    setup = assignment_setup
    assignment_id, attempt_id = prepare_answer_attempt(client, setup)

    response = send_attempt_answers(
        client, setup, assignment_id, attempt_id,
        submit=submit,
        student_index=student_index,
        answers={"1": "A"},
    )
    assert response.status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {"answers": []},
        {"answers": {"1": "E"}},
        {"answers": {"1": 1}},
        {"answers": {"21": "A"}},
        {"answers": {"6": "A"}},
        {"answers": {}, "score": 5},
    ],
)
@pytest.mark.parametrize("submit", [False, True])
def test_assignment_answers_reject_invalid_input(
    client, app, assignment_setup, payload, submit
):
    setup = assignment_setup
    assignment_id, attempt_id = prepare_answer_attempt(client, setup)
    suffix = "submit" if submit else "answers"

    response = client.open(
        f"/api/quiz-assignments/{assignment_id}"
        f"/attempts/{attempt_id}/{suffix}",
        method="POST" if submit else "PATCH",
        headers=setup["students"][0]["headers"],
        json=payload,
    )
    assert response.status_code == 400

    with app.app_context():
        attempt = db.session.get(QuizAssignmentAttempt, attempt_id)
        assert attempt is not None
        assert attempt.answers == {}
        assert attempt.submitted_at is None


@pytest.mark.parametrize("submit", [False, True])
@pytest.mark.parametrize("expiry_source", ["timer", "deadline"])
def test_expired_assignment_grades_only_saved_answers(
    client, app, assignment_setup, submit, expiry_source
):
    setup = assignment_setup
    assignment_id, attempt_id = prepare_answer_attempt(client, setup)

    saved = send_attempt_answers(
        client, setup, assignment_id, attempt_id,
        answers={"1": "A"},
    )
    assert saved.status_code == 200

    with app.app_context():
        attempt = db.session.get(QuizAssignmentAttempt, attempt_id)
        assignment = db.session.get(QuizAssignment, assignment_id)
        assert attempt is not None
        assert assignment is not None
        now = datetime.now(timezone.utc)

        attempt.started_at = now - timedelta(minutes=10)

        if expiry_source == "timer":
            attempt.expires_at = now - timedelta(seconds=1)
        else:
            assignment.available_at = now - timedelta(hours=1)
            assignment.deadline_at = now - timedelta(seconds=1)
            assignment.review_at = assignment.deadline_at

        db.session.commit()

    response = send_attempt_answers(
        client, setup, assignment_id, attempt_id,
        submit=submit,
        answers={str(index): "A" for index in range(1, 6)},
    )
    assert response.status_code == 200
    assert response.get_json()["result"]["score"] == 1

    with app.app_context():
        attempt = db.session.get(QuizAssignmentAttempt, attempt_id)
        assert attempt is not None
        assert attempt.answers == {"1": "A"}
        assert attempt.submitted_at is not None


def test_assignment_empty_submission_scores_zero(
    client, assignment_setup
):
    setup = assignment_setup
    assignment_id, attempt_id = prepare_answer_attempt(client, setup)

    response = send_attempt_answers(
        client, setup, assignment_id, attempt_id,
        submit=True,
        answers={},
    )
    assert response.status_code == 200
    assert response.get_json()["result"]["score"] == 0


@pytest.mark.parametrize("submit", [False, True])
def test_assignment_answers_failure_rolls_back(
    client, app, assignment_setup, monkeypatch, submit
):
    setup = assignment_setup
    assignment_id, attempt_id = prepare_answer_attempt(client, setup)

    with monkeypatch.context() as patch:
        patch.setattr(
            db.session,
            "commit",
            Mock(side_effect=SQLAlchemyError("Test commit failure")),
        )
        response = send_attempt_answers(
            client, setup, assignment_id, attempt_id,
            submit=submit,
            answers={"1": "A"},
        )

    assert response.status_code == 500

    with app.app_context():
        attempt = db.session.get(QuizAssignmentAttempt, attempt_id)
        assert attempt is not None
        assert attempt.answers == {}
        assert attempt.score is None
        assert attempt.submitted_at is None
        assert attempt.quiz_attempt_id is None
        assert db.session.scalar(
            db.select(db.func.count()).select_from(QuizAttempt)
        ) == 0

    retry = send_attempt_answers(
        client, setup, assignment_id, attempt_id,
        submit=submit,
        answers={"1": "A"},
    )
    assert retry.status_code == 200


def get_assignment_review(
    client, setup, assignment_id, attempt_id, student_index=0
):
    return client.get(
        f"/api/quiz-assignments/{assignment_id}"
        f"/attempts/{attempt_id}/review",
        headers=setup["students"][student_index]["headers"],
    )


def prepare_submitted_review(client, setup):
    assignment_id, attempt_id = prepare_answer_attempt(client, setup)

    response = send_attempt_answers(
        client,
        setup,
        assignment_id,
        attempt_id,
        submit=True,
        answers={"1": "A", "2": "B"},
    )
    assert response.status_code == 200

    return assignment_id, attempt_id


def unlock_assignment_review(app, assignment_id):
    with app.app_context():
        assignment = db.session.get(QuizAssignment, assignment_id)
        assert assignment is not None

        now = datetime.now(timezone.utc)
        assignment.available_at = now - timedelta(hours=2)
        assignment.deadline_at = now - timedelta(hours=1)
        assignment.review_at = now - timedelta(minutes=30)
        db.session.commit()


def test_assignment_review_requires_login(client):
    response = client.get(
        "/api/quiz-assignments/unknown/attempts/unknown/review"
    )
    assert response.status_code == 401


def test_teacher_cannot_use_student_review(client, assignment_setup):
    response = client.get(
        "/api/quiz-assignments/unknown/attempts/unknown/review",
        headers=assignment_setup["teacher"]["headers"],
    )
    assert response.status_code == 403


def test_assignment_review_waits_until_review_time(
    client, assignment_setup
):
    setup = assignment_setup
    assignment_id, attempt_id = prepare_submitted_review(client, setup)

    response = get_assignment_review(
        client, setup, assignment_id, attempt_id
    )
    assert response.status_code == 409
    assert "review_at" in response.get_json()

    body = response.get_data(as_text=True)
    assert "correct_option" not in body
    assert "explanation" not in body
    assert "Binary uses base 2." not in body


def test_student_can_review_submitted_answers(
    client, app, assignment_setup
):
    setup = assignment_setup
    assignment_id, attempt_id = prepare_submitted_review(client, setup)
    unlock_assignment_review(app, assignment_id)

    response = get_assignment_review(
        client, setup, assignment_id, attempt_id
    )
    assert response.status_code == 200

    review = response.get_json()["review"]
    assert review["id"] == attempt_id
    assert review["assignment_id"] == assignment_id
    assert review["score"] == 1
    assert review["total_questions"] == 5
    assert review["quiz_title"] == "Published Assignment Quiz"

    questions = review["questions"]
    assert len(questions) == 5
    by_id = {question["id"]: question for question in questions}

    assert by_id["1"]["selected_option"] == "A"
    assert by_id["1"]["correct_option"] == "A"
    assert by_id["1"]["is_correct"] is True
    assert by_id["1"]["explanation"] == "Binary uses base 2."

    assert by_id["2"]["selected_option"] == "B"
    assert by_id["2"]["is_correct"] is False

    assert by_id["3"]["selected_option"] is None
    assert by_id["3"]["is_correct"] is False

    # Reviewing must not create another progress record.
    with app.app_context():
        assert db.session.scalar(
            db.select(db.func.count()).select_from(QuizAttempt)
        ) == 1


def test_assignment_review_rejects_unsubmitted_attempt(
    client, app, assignment_setup
):
    setup = assignment_setup
    assignment_id, attempt_id = prepare_answer_attempt(client, setup)
    unlock_assignment_review(app, assignment_id)

    response = get_assignment_review(
        client, setup, assignment_id, attempt_id
    )
    assert response.status_code == 409
    assert "correct_option" not in response.get_data(as_text=True)


@pytest.mark.parametrize(
    "case",
    ["other-student", "outsider", "missing-attempt", "missing-assignment"],
)
def test_assignment_review_rejects_inaccessible_attempt(
    client, app, assignment_setup, case
):
    setup = assignment_setup
    assignment_id, attempt_id = prepare_submitted_review(client, setup)
    unlock_assignment_review(app, assignment_id)
    student_index = 0

    if case == "other-student":
        student_index = 1
    elif case == "outsider":
        student_index = 2
    elif case == "missing-attempt":
        attempt_id = str(uuid4())
    else:
        assignment_id = str(uuid4())

    response = get_assignment_review(
        client, setup, assignment_id, attempt_id, student_index
    )
    assert response.status_code == 404
    assert "correct_option" not in response.get_data(as_text=True)


@pytest.mark.parametrize("case", ["draft", "invalid-questions"])
def test_assignment_review_rejects_invalid_saved_quiz(
    client, app, assignment_setup, case
):
    setup = assignment_setup
    assignment_id, attempt_id = prepare_submitted_review(client, setup)
    unlock_assignment_review(app, assignment_id)

    with app.app_context():
        quiz = db.session.get(TeacherQuiz, setup["quiz_id"])
        assert quiz is not None

        if case == "draft":
            quiz.status = "draft"
        else:
            quiz.questions = []

        db.session.commit()

    response = get_assignment_review(
        client, setup, assignment_id, attempt_id
    )
    assert response.status_code == 409

def test_my_assignment_attempts_require_login(client):
    response = client.get("/api/quiz-assignments/unknown/attempts")
    assert response.status_code == 401


def test_teacher_cannot_list_student_assignment_attempts(
    client, assignment_setup
):
    response = client.get(
        "/api/quiz-assignments/unknown/attempts",
        headers=assignment_setup["teacher"]["headers"],
    )
    assert response.status_code == 403


def test_my_assignment_attempts_empty_before_start(
    client, assignment_setup
):
    setup = assignment_setup
    assignment_id = create_assignment_for_list_test(client, setup)

    response = client.get(
        f"/api/quiz-assignments/{assignment_id}/attempts",
        headers=setup["students"][0]["headers"],
    )
    assert response.status_code == 200
    assert response.get_json()["attempts"] == []


def test_my_assignment_attempts_returns_saved_score(
    client, app, assignment_setup
):
    setup = assignment_setup
    assignment_id, attempt_id = prepare_submitted_review(client, setup)

    response = client.get(
        f"/api/quiz-assignments/{assignment_id}/attempts",
        headers=setup["students"][0]["headers"],
    )
    assert response.status_code == 200
    items = response.get_json()["attempts"]
    assert len(items) == 1

    item = items[0]
    assert item["id"] == attempt_id
    assert item["status"] == "submitted"
    assert item["score"] == 1
    assert item["total_questions"] == 5
    assert item["submitted_at"] is not None
    assert item["can_review"] is False

    for field in ("questions", "answers", "correct_option", "explanation"):
        assert field not in item

    unlock_assignment_review(app, assignment_id)

    response = client.get(
        f"/api/quiz-assignments/{assignment_id}/attempts",
        headers=setup["students"][0]["headers"],
    )
    assert response.status_code == 200
    assert response.get_json()["attempts"][0]["can_review"] is True


def test_my_assignment_attempts_excludes_other_students(
    client, assignment_setup
):
    setup = assignment_setup
    assignment_id, _ = prepare_submitted_review(client, setup)

    # This student received the assignment but has not attempted it.
    response = client.get(
        f"/api/quiz-assignments/{assignment_id}/attempts",
        headers=setup["students"][1]["headers"],
    )
    assert response.status_code == 200
    assert response.get_json()["attempts"] == []


@pytest.mark.parametrize("case", ["outsider", "missing"])
def test_my_assignment_attempts_rejects_inaccessible_assignment(
    client, assignment_setup, case
):
    setup = assignment_setup
    assignment_id = create_assignment_for_list_test(client, setup)
    student_index = 2

    if case == "missing":
        assignment_id = str(uuid4())
        student_index = 0

    response = client.get(
        f"/api/quiz-assignments/{assignment_id}/attempts",
        headers=setup["students"][student_index]["headers"],
    )
    assert response.status_code == 404


def test_my_assignment_attempts_status_and_order(
    client, app, assignment_setup
):
    setup = assignment_setup
    assignment_id, _ = prepare_submitted_review(client, setup)

    with app.app_context():
        assignment = db.session.get(QuizAssignment, assignment_id)
        assert assignment is not None
        assignment.max_attempts = 3

        now = datetime.now(timezone.utc)

        expired = QuizAssignmentAttempt(
            assignment_id=assignment_id,
            student_id=setup["students"][0]["id"],
            attempt_number=2,
            started_at=now - timedelta(minutes=40),
            expires_at=now - timedelta(minutes=10),
            total_questions=5,
        )
        active = QuizAssignmentAttempt(
            assignment_id=assignment_id,
            student_id=setup["students"][0]["id"],
            attempt_number=3,
            started_at=now,
            expires_at=now + timedelta(minutes=30),
            total_questions=5,
        )
        db.session.add_all([expired, active])
        db.session.commit()

    response = client.get(
        f"/api/quiz-assignments/{assignment_id}/attempts",
        headers=setup["students"][0]["headers"],
    )
    assert response.status_code == 200
    items = response.get_json()["attempts"]

    assert [item["attempt_number"] for item in items] == [3, 2, 1]
    assert [item["status"] for item in items] == [
        "in_progress", "expired", "submitted"
    ]
    assert items[0]["score"] is None
    assert items[1]["score"] is None
    assert items[0]["can_review"] is False
    assert items[1]["can_review"] is False

    # Listing an expired attempt must not submit or grade it.
    with app.app_context():
        assert db.session.scalar(
            db.select(db.func.count()).select_from(QuizAttempt)
        ) == 1

def get_teacher_results(client, setup, assignment_id, *, page=1):
    return client.get(
        f"/api/quiz-assignments/{assignment_id}/results",
        headers=setup["teacher"]["headers"],
        query_string={"page": page},
    )


def test_assignment_results_require_login(client):
    response = client.get(
        "/api/quiz-assignments/unknown/results"
    )

    assert response.status_code == 401


def test_student_cannot_view_teacher_assignment_results(
    client, assignment_setup
):
    setup = assignment_setup
    assignment_id = create_assignment_for_list_test(client, setup)

    response = client.get(
        f"/api/quiz-assignments/{assignment_id}/results",
        headers=setup["students"][0]["headers"],
    )

    assert response.status_code == 403


@pytest.mark.parametrize("case", [
    "missing",
    "other-teacher",
    "classroom-owner-changed",
    "quiz-owner-changed",
])
def test_assignment_results_reject_inaccessible_assignment(
    client, app, assignment_setup, case
):
    setup = assignment_setup
    assignment_id = create_assignment_for_list_test(client, setup)
    headers = setup["teacher"]["headers"]

    if case == "missing":
        assignment_id = str(uuid4())
    elif case == "other-teacher":
        headers = setup["other_teacher"]["headers"]
    else:
        with app.app_context():
            if case == "classroom-owner-changed":
                classroom = db.session.get(
                    Classroom, setup["classroom_id"]
                )
                assert classroom is not None
                classroom.teacher_id = setup["other_teacher"]["id"]
            else:
                quiz = db.session.get(TeacherQuiz, setup["quiz_id"])
                assert quiz is not None
                quiz.teacher_id = setup["other_teacher"]["id"]

            db.session.commit()

    response = client.get(
        f"/api/quiz-assignments/{assignment_id}/results",
        headers=headers,
    )

    assert response.status_code == 404
    assert "students" not in response.get_json()


def test_assignment_results_include_unattempted_recipients(
    client, assignment_setup
):
    setup = assignment_setup
    assignment_id = create_assignment_for_list_test(client, setup)

    response = get_teacher_results(client, setup, assignment_id)

    assert response.status_code == 200
    data = response.get_json()

    assert data["assignment"]["id"] == assignment_id
    assert data["assignment"]["recipient_count"] == 2
    assert data["assignment"]["quiz_title"] == "Published Assignment Quiz"
    assert data["assignment"]["classroom_name"] == "HSC Assignment Class"

    students = data["students"]

    assert [item["student_id"] for item in students] == [
        setup["students"][0]["id"],
        setup["students"][1]["id"],
    ]

    for student in students:
        assert student["student_name"]
        assert student["latest_status"] == "not_started"
        assert student["attempts_used"] == 0
        assert student["submitted_attempts"] == 0
        assert student["best_score"] is None
        assert student["best_total_questions"] is None
        assert student["attempts"] == []

    assert data["pagination"] == {
        "page": 1,
        "page_size": 20,
        "has_more": False,
    }


def test_assignment_results_return_scores_and_best_attempt(
    client, assignment_setup
):
    setup = assignment_setup
    assignment_id, first_id = prepare_submitted_review(client, setup)

    started = start_assignment(client, setup, assignment_id)
    assert started.status_code == 201
    second_id = started.get_json()["attempt"]["id"]

    submitted = send_attempt_answers(
        client,
        setup,
        assignment_id,
        second_id,
        submit=True,
        answers={"1": "A", "2": "A", "3": "A"},
    )
    assert submitted.status_code == 200

    response = get_teacher_results(client, setup, assignment_id)

    assert response.status_code == 200
    students = response.get_json()["students"]
    student = next(
        item for item in students
        if item["student_id"] == setup["students"][0]["id"]
    )

    assert student["latest_status"] == "submitted"
    assert student["attempts_used"] == 2
    assert student["submitted_attempts"] == 2
    assert student["best_score"] == 3
    assert student["best_total_questions"] == 5
    assert [item["id"] for item in student["attempts"]] == [
        second_id, first_id
    ]
    assert [item["score"] for item in student["attempts"]] == [3, 1]

    for attempt in student["attempts"]:
        assert attempt["submitted_at"] is not None
        assert attempt["total_questions"] == 5
        assert "answers" not in attempt
        assert "questions" not in attempt
        assert "correct_option" not in attempt
        assert "explanation" not in attempt


def test_assignment_results_keep_best_score_when_latest_is_lower(
    client, assignment_setup
):
    setup = assignment_setup
    assignment_id, _ = prepare_submitted_review(client, setup)

    started = start_assignment(client, setup, assignment_id)
    assert started.status_code == 201
    second_id = started.get_json()["attempt"]["id"]

    submitted = send_attempt_answers(
        client,
        setup,
        assignment_id,
        second_id,
        submit=True,
        answers={},
    )
    assert submitted.status_code == 200

    response = get_teacher_results(client, setup, assignment_id)
    assert response.status_code == 200

    student = next(
        item for item in response.get_json()["students"]
        if item["student_id"] == setup["students"][0]["id"]
    )

    assert student["attempts"][0]["score"] == 0
    assert student["best_score"] == 1
    assert student["submitted_attempts"] == 2


def test_assignment_results_show_active_and_expired_without_grading(
    client, app, assignment_setup
):
    setup = assignment_setup
    assignment_id = create_assignment_for_list_test(client, setup)

    with app.app_context():
        now = datetime.now(timezone.utc)

        expired = QuizAssignmentAttempt(
            assignment_id=assignment_id,
            student_id=setup["students"][0]["id"],
            attempt_number=1,
            started_at=now - timedelta(minutes=40),
            expires_at=now - timedelta(minutes=10),
            total_questions=5,
        )
        active = QuizAssignmentAttempt(
            assignment_id=assignment_id,
            student_id=setup["students"][0]["id"],
            attempt_number=2,
            started_at=now,
            expires_at=now + timedelta(minutes=30),
            total_questions=5,
        )

        db.session.add_all([expired, active])
        db.session.commit()

    response = get_teacher_results(client, setup, assignment_id)
    assert response.status_code == 200

    student = next(
        item for item in response.get_json()["students"]
        if item["student_id"] == setup["students"][0]["id"]
    )

    assert student["latest_status"] == "in_progress"
    assert student["attempts_used"] == 2
    assert student["submitted_attempts"] == 0
    assert student["best_score"] is None
    assert [item["status"] for item in student["attempts"]] == [
        "in_progress", "expired"
    ]

    for attempt in student["attempts"]:
        assert attempt["score"] is None
        assert attempt["submitted_at"] is None

    with app.app_context():
        assert db.session.scalar(
            db.select(db.func.count()).select_from(QuizAttempt)
        ) == 0


def test_assignment_results_use_saved_recipient_snapshot(
    client, app, assignment_setup
):
    setup = assignment_setup
    assignment_id = create_assignment_for_list_test(
        client,
        setup,
        student_ids=[setup["students"][0]["id"]],
    )

    with app.app_context():
        membership = db.session.scalar(
            db.select(ClassMembership).where(
                ClassMembership.classroom_id == setup["classroom_id"],
                ClassMembership.student_id == setup["students"][0]["id"],
            )
        )
        assert membership is not None
        db.session.delete(membership)

        db.session.add(
            ClassMembership(
                classroom_id=setup["classroom_id"],
                student_id=setup["students"][2]["id"],
            )
        )
        db.session.commit()

    response = get_teacher_results(client, setup, assignment_id)
    assert response.status_code == 200
    data = response.get_json()

    assert data["assignment"]["recipient_count"] == 1
    assert [item["student_id"] for item in data["students"]] == [
        setup["students"][0]["id"]
    ]


@pytest.mark.parametrize("page", ["0", "-1", "abc", "10001"])
def test_assignment_results_reject_invalid_page(
    client, assignment_setup, page
):
    setup = assignment_setup
    assignment_id = create_assignment_for_list_test(client, setup)

    response = get_teacher_results(
        client, setup, assignment_id, page=page
    )

    assert response.status_code == 400


def test_assignment_results_paginate_students(
    client, app, assignment_setup
):
    setup = assignment_setup
    assignment_id = create_assignment_for_list_test(client, setup)

    # Add recipient records directly to isolate results pagination.
    with app.app_context():
        for index in range(19):
            student = User(
                name=f"Results Student {index}",
                email=f"results-page-{index}@example.com",
                password_hash="unused-test-password-hash",
                role="student",
            )
            db.session.add(student)
            db.session.flush()

            db.session.add(
                QuizAssignmentRecipient(
                    assignment_id=assignment_id,
                    student_id=student.id,
                )
            )

        db.session.commit()

    first = get_teacher_results(client, setup, assignment_id, page=1)
    second = get_teacher_results(client, setup, assignment_id, page=2)
    third = get_teacher_results(client, setup, assignment_id, page=3)

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 200

    first_data = first.get_json()
    second_data = second.get_json()
    third_data = third.get_json()

    assert first_data["assignment"]["recipient_count"] == 21
    assert len(first_data["students"]) == 20
    assert first_data["pagination"]["has_more"] is True

    assert len(second_data["students"]) == 1
    assert second_data["pagination"]["has_more"] is False

    first_ids = {
        item["student_id"] for item in first_data["students"]
    }
    second_ids = {
        item["student_id"] for item in second_data["students"]
    }
    assert first_ids.isdisjoint(second_ids)

    assert third_data["students"] == []
    assert third_data["pagination"]["has_more"] is False

def get_teacher_submission_review(
    client,
    setup,
    assignment_id,
    attempt_id,
    *,
    user=None,
):
    reviewer = setup["teacher"] if user is None else user

    return client.get(
        f"/api/quiz-assignments/{assignment_id}"
        f"/attempts/{attempt_id}/teacher-review",
        headers=reviewer["headers"],
    )


def assert_no_review_answers(response):
    body = response.get_data(as_text=True)

    assert "correct_option" not in body
    assert "explanation" not in body
    assert "Binary uses base 2." not in body


def test_teacher_submission_review_requires_login(client):
    response = client.get(
        "/api/quiz-assignments/unknown"
        "/attempts/unknown/teacher-review"
    )

    assert response.status_code == 401
    assert_no_review_answers(response)


@pytest.mark.parametrize("student_index", [0, 1, 2])
def test_students_cannot_use_teacher_submission_review(
    client,
    assignment_setup,
    student_index,
):
    setup = assignment_setup
    assignment_id, attempt_id = prepare_submitted_review(
        client,
        setup,
    )

    response = get_teacher_submission_review(
        client,
        setup,
        assignment_id,
        attempt_id,
        user=setup["students"][student_index],
    )

    assert response.status_code == 403
    assert_no_review_answers(response)


def test_owner_reviews_submission_before_student_review_time(
    client,
    app,
    assignment_setup,
):
    setup = assignment_setup
    assignment_id, attempt_id = prepare_submitted_review(
        client,
        setup,
    )

    # Student review remains locked.
    student_response = get_assignment_review(
        client,
        setup,
        assignment_id,
        attempt_id,
    )

    assert student_response.status_code == 409
    assert_no_review_answers(student_response)

    for _ in range(2):
        response = get_teacher_submission_review(
            client,
            setup,
            assignment_id,
            attempt_id,
        )

        assert response.status_code == 200

        review = response.get_json()["review"]

        assert review["id"] == attempt_id
        assert review["assignment_id"] == assignment_id
        assert review["student_id"] == setup["students"][0]["id"]
        assert review["student_name"] == "Assignment Student"
        assert review["classroom_id"] == setup["classroom_id"]
        assert review["classroom_name"] == "HSC Assignment Class"
        assert review["quiz_title"] == "Published Assignment Quiz"
        assert review["response_language"] == "english"
        assert review["attempt_number"] == 1
        assert review["score"] == 1
        assert review["total_questions"] == 5
        assert review["started_at"]
        assert review["submitted_at"]

        questions = review["questions"]

        assert len(questions) == 5

        by_id = {
            question["id"]: question
            for question in questions
        }

        assert by_id["1"]["question_text"] == "Question 1"
        assert by_id["1"]["option_a"] == "2"
        assert by_id["1"]["option_b"] == "8"
        assert by_id["1"]["option_c"] == "10"
        assert by_id["1"]["option_d"] == "16"
        assert by_id["1"]["selected_option"] == "A"
        assert by_id["1"]["correct_option"] == "A"
        assert by_id["1"]["is_correct"] is True
        assert by_id["1"]["explanation"] == "Binary uses base 2."

        assert by_id["2"]["selected_option"] == "B"
        assert by_id["2"]["is_correct"] is False

        assert by_id["3"]["selected_option"] is None
        assert by_id["3"]["is_correct"] is False

    # Repeated review must not modify or regrade the attempt.
    with app.app_context():
        attempt = db.session.get(QuizAssignmentAttempt, attempt_id)

        assert attempt is not None
        assert attempt.answers == {"1": "A", "2": "B"}
        assert attempt.score == 1

        assert db.session.scalar(
            db.select(db.func.count()).select_from(QuizAttempt)
        ) == 1


@pytest.mark.parametrize(
    "case",
    [
        "other-teacher",
        "missing-assignment",
        "missing-attempt",
        "attempt-from-other-assignment",
        "quiz-owner-changed",
        "class-owner-changed",
        "missing-recipient",
    ],
)
def test_teacher_review_rejects_inaccessible_submission(
    client,
    app,
    assignment_setup,
    case,
):
    setup = assignment_setup
    assignment_id, attempt_id = prepare_submitted_review(
        client,
        setup,
    )
    reviewer = setup["teacher"]

    if case == "other-teacher":
        reviewer = setup["other_teacher"]

    elif case == "missing-assignment":
        assignment_id = str(uuid4())

    elif case == "missing-attempt":
        attempt_id = str(uuid4())

    elif case == "attempt-from-other-assignment":
        # Both assignments belong to this teacher, but the attempt
        # must still match the assignment ID in the URL.
        assignment_id = create_assignment_for_list_test(
            client,
            setup,
        )

    else:
        with app.app_context():
            if case == "quiz-owner-changed":
                quiz = db.session.get(TeacherQuiz, setup["quiz_id"])

                assert quiz is not None
                quiz.teacher_id = setup["other_teacher"]["id"]

            elif case == "class-owner-changed":
                classroom = db.session.get(
                    Classroom,
                    setup["classroom_id"],
                )

                assert classroom is not None
                classroom.teacher_id = setup["other_teacher"]["id"]

            else:
                recipient = db.session.scalar(
                    db.select(QuizAssignmentRecipient).where(
                        QuizAssignmentRecipient.assignment_id
                        == assignment_id,
                        QuizAssignmentRecipient.student_id
                        == setup["students"][0]["id"],
                    )
                )

                assert recipient is not None
                db.session.delete(recipient)

            db.session.commit()

    response = get_teacher_submission_review(
        client,
        setup,
        assignment_id,
        attempt_id,
        user=reviewer,
    )

    assert response.status_code == 404
    assert_no_review_answers(response)


def test_teacher_review_rejects_unsubmitted_attempt(
    client,
    assignment_setup,
):
    setup = assignment_setup
    assignment_id, attempt_id = prepare_answer_attempt(
        client,
        setup,
    )

    response = get_teacher_submission_review(
        client,
        setup,
        assignment_id,
        attempt_id,
    )

    assert response.status_code == 409
    assert response.get_json()["error"] == (
        "This attempt has not been submitted."
    )
    assert_no_review_answers(response)


def test_teacher_review_keeps_access_after_student_leaves(
    client,
    app,
    assignment_setup,
):
    setup = assignment_setup
    assignment_id, attempt_id = prepare_submitted_review(
        client,
        setup,
    )

    with app.app_context():
        membership = db.session.scalar(
            db.select(ClassMembership).where(
                ClassMembership.classroom_id
                == setup["classroom_id"],
                ClassMembership.student_id
                == setup["students"][0]["id"],
            )
        )

        assert membership is not None
        db.session.delete(membership)
        db.session.commit()

    response = get_teacher_submission_review(
        client,
        setup,
        assignment_id,
        attempt_id,
    )

    assert response.status_code == 200
    assert response.get_json()["review"]["student_id"] == (
        setup["students"][0]["id"]
    )


@pytest.mark.parametrize(
    "case",
    ["draft", "invalid-questions", "question-count-mismatch"],
)
def test_teacher_review_rejects_invalid_quiz(
    client,
    app,
    assignment_setup,
    case,
):
    setup = assignment_setup
    assignment_id, attempt_id = prepare_submitted_review(
        client,
        setup,
    )

    with app.app_context():
        quiz = db.session.get(TeacherQuiz, setup["quiz_id"])

        assert quiz is not None

        if case == "draft":
            quiz.status = "draft"

        elif case == "invalid-questions":
            quiz.questions = []

        else:
            # Still valid quiz JSON, but incompatible with this attempt.
            quiz.questions = quiz.questions[:4]
            quiz.question_count = 4

        db.session.commit()

    response = get_teacher_submission_review(
        client,
        setup,
        assignment_id,
        attempt_id,
    )

    assert response.status_code == 409
    assert_no_review_answers(response)


def test_teacher_review_handles_database_failure(
    client,
    app,
    assignment_setup,
    monkeypatch,
):
    setup = assignment_setup
    assignment_id, attempt_id = prepare_submitted_review(
        client,
        setup,
    )

    original_scalar = db.session.scalar

    def fail_assignment_query(statement, *args, **kwargs):
        # Fail only the route's assignment lookup.
        # JWT authentication queries still use the real database.
        entities = [
            description.get("entity")
            for description in statement.column_descriptions
        ]

        if any(entity is QuizAssignment for entity in entities):
            raise SQLAlchemyError("Test assignment read failure")

        return original_scalar(statement, *args, **kwargs)

    with monkeypatch.context() as patched:
        patched.setattr(
            db.session,
            "scalar",
            fail_assignment_query,
        )

        response = get_teacher_submission_review(
            client,
            setup,
            assignment_id,
            attempt_id,
        )

    assert response.status_code == 500
    assert response.get_json()["error"] == (
        "Could not load student submission. Try again later."
    )
    assert_no_review_answers(response)

    response = get_teacher_submission_review(
        client,
        setup,
        assignment_id,
        attempt_id,
    )

    assert response.status_code == 200

def get_mistake_report(
    client,
    setup,
    assignment_id,
    *,
    user=None,
    **query,
):
    return client.get(
        f"/api/quiz-assignments/{assignment_id}/mistake-report",
        headers=(user or setup["teacher"])["headers"],
        query_string=query,
    )


def submit_report_attempt(
    client,
    setup,
    assignment_id,
    answers,
    *,
    student_index=0,
):
    started = start_assignment(
        client,
        setup,
        assignment_id,
        student_index=student_index,
    )
    assert started.status_code == 201

    attempt_id = started.get_json()["attempt"]["id"]

    submitted = send_attempt_answers(
        client,
        setup,
        assignment_id,
        attempt_id,
        submit=True,
        answers=answers,
        student_index=student_index,
    )
    assert submitted.status_code == 200

    return attempt_id


def test_mistake_report_requires_login(client):
    response = client.get(
        f"/api/quiz-assignments/{uuid4()}/mistake-report"
    )
    assert response.status_code == 401


@pytest.mark.parametrize("student_index", [0, 1, 2])
def test_mistake_report_rejects_students(
    client,
    assignment_setup,
    student_index,
):
    setup = assignment_setup
    assignment_id = create_assignment_for_list_test(client, setup)

    response = get_mistake_report(
        client,
        setup,
        assignment_id,
        user=setup["students"][student_index],
    )

    assert response.status_code == 403
    assert "questions" not in response.get_json()


@pytest.mark.parametrize(
    "case",
    [
        "missing",
        "other-teacher",
        "quiz-owner-changed",
        "class-owner-changed",
    ],
)
def test_mistake_report_enforces_both_owners(
    client,
    app,
    assignment_setup,
    case,
):
    setup = assignment_setup
    assignment_id = create_assignment_for_list_test(client, setup)
    reviewer = setup["teacher"]

    if case == "missing":
        assignment_id = str(uuid4())
    elif case == "other-teacher":
        reviewer = setup["other_teacher"]
    else:
        with app.app_context():
            if case == "quiz-owner-changed":
                quiz = db.session.get(
                    TeacherQuiz, setup["quiz_id"]
                )
                assert quiz is not None
                quiz.teacher_id = setup["other_teacher"]["id"]
            else:
                classroom = db.session.get(
                    Classroom, setup["classroom_id"]
                )
                assert classroom is not None
                classroom.teacher_id = setup["other_teacher"]["id"]

            db.session.commit()

    response = get_mistake_report(
        client,
        setup,
        assignment_id,
        user=reviewer,
    )

    assert response.status_code == 404
    assert "questions" not in response.get_json()


def test_mistake_report_without_attempts(
    client,
    assignment_setup,
):
    setup = assignment_setup
    assignment_id = create_assignment_for_list_test(client, setup)

    response = get_mistake_report(client, setup, assignment_id)

    assert response.status_code == 200
    report = response.get_json()

    assert report["summary"] == {
        "recipient_count": 2,
        "submitted_students": 0,
        "not_started_students": 2,
        "not_submitted_students": 0,
        "in_progress_students": 0,
        "expired_without_submission_students": 0,
    }
    assert report["most_missed_question_ids"] == []
    assert len(report["questions"]) == 5

    for question in report["questions"]:
        assert question["assessed_students"] == 0
        assert question["correct_count"] == 0
        assert question["wrong_count"] == 0
        assert question["unanswered_count"] == 0
        assert question["wrong_percentage"] is None

    assert all(
        student["participation_status"] == "not_started"
        for student in report["students"]
    )


def test_mistake_report_counts_correct_wrong_and_unanswered(
    client,
    assignment_setup,
):
    setup = assignment_setup
    assignment_id = create_assignment_for_list_test(client, setup)

    submit_report_attempt(
        client,
        setup,
        assignment_id,
        {"1": "A", "2": "B", "4": "A"},
    )
    submit_report_attempt(
        client,
        setup,
        assignment_id,
        {"1": "B", "2": "B", "3": "A", "4": "A"},
        student_index=1,
    )

    response = get_mistake_report(client, setup, assignment_id)

    assert response.status_code == 200
    report = response.get_json()
    questions = {
        question["id"]: question
        for question in report["questions"]
    }

    assert report["summary"]["submitted_students"] == 2
    assert report["attempt_policy"] == (
        "latest_submitted_per_student"
    )

    assert questions["1"]["correct_count"] == 1
    assert questions["1"]["wrong_count"] == 1
    assert questions["1"]["wrong_percentage"] == 50.0

    assert questions["2"]["wrong_count"] == 2
    assert questions["2"]["wrong_percentage"] == 100.0

    assert questions["3"]["correct_count"] == 1
    assert questions["3"]["unanswered_count"] == 1

    assert questions["4"]["correct_count"] == 2
    assert questions["4"]["wrong_count"] == 0

    assert questions["5"]["unanswered_count"] == 2
    assert questions["5"]["wrong_count"] == 0

    assert report["most_missed_question_ids"] == ["2", "1"]

    for question in questions.values():
        assert (
            question["correct_count"]
            + question["wrong_count"]
            + question["unanswered_count"]
        ) == question["assessed_students"] == 2


def test_mistake_report_uses_latest_submission_once(
    client,
    assignment_setup,
):
    setup = assignment_setup
    assignment_id = create_assignment_for_list_test(client, setup)

    submit_report_attempt(
        client,
        setup,
        assignment_id,
        {"1": "A"},
    )
    submit_report_attempt(
        client,
        setup,
        assignment_id,
        {"1": "B"},
    )

    response = get_mistake_report(client, setup, assignment_id)

    assert response.status_code == 200
    report = response.get_json()
    question = report["questions"][0]

    assert report["summary"]["submitted_students"] == 1
    assert question["assessed_students"] == 1
    assert question["correct_count"] == 0
    assert question["wrong_count"] == 1


def test_mistake_report_ignores_unsubmitted_retry_answers(
    client,
    assignment_setup,
):
    setup = assignment_setup
    assignment_id = create_assignment_for_list_test(client, setup)

    submit_report_attempt(
        client,
        setup,
        assignment_id,
        {"1": "A"},
    )

    retry = start_assignment(client, setup, assignment_id)
    assert retry.status_code == 201
    retry_id = retry.get_json()["attempt"]["id"]

    saved = send_attempt_answers(
        client,
        setup,
        assignment_id,
        retry_id,
        answers={"1": "B"},
    )
    assert saved.status_code == 200

    response = get_mistake_report(client, setup, assignment_id)

    assert response.status_code == 200
    report = response.get_json()
    question = report["questions"][0]

    assert question["correct_count"] == 1
    assert question["wrong_count"] == 0
    assert report["summary"]["submitted_students"] == 1

    student = next(
        item for item in report["students"]
        if item["student_id"] == setup["students"][0]["id"]
    )
    assert student["participation_status"] == "submitted"
    assert student["latest_attempt_status"] == "in_progress"


@pytest.mark.parametrize("expired", [False, True])
def test_mistake_report_distinguishes_unsubmitted_attempts(
    client,
    app,
    assignment_setup,
    expired,
):
    setup = assignment_setup
    assignment_id, attempt_id = prepare_answer_attempt(
        client, setup
    )

    saved = send_attempt_answers(
        client,
        setup,
        assignment_id,
        attempt_id,
        answers={"1": "B"},
    )
    assert saved.status_code == 200

    if expired:
        with app.app_context():
            attempt = db.session.get(
                QuizAssignmentAttempt, attempt_id
            )
            assert attempt is not None
            now = datetime.now(timezone.utc)
            attempt.started_at = now - timedelta(minutes=31)
            attempt.expires_at = now - timedelta(minutes=1)
            db.session.commit()

    response = get_mistake_report(client, setup, assignment_id)

    assert response.status_code == 200
    report = response.get_json()
    summary = report["summary"]

    assert summary["submitted_students"] == 0
    assert summary["not_started_students"] == 1
    assert summary["not_submitted_students"] == 1
    assert summary["in_progress_students"] == (
        0 if expired else 1
    )
    assert summary["expired_without_submission_students"] == (
        1 if expired else 0
    )

    assert all(
        question["assessed_students"] == 0
        for question in report["questions"]
    )

    with app.app_context():
        attempt = db.session.get(
            QuizAssignmentAttempt, attempt_id
        )
        assert attempt is not None
        assert attempt.submitted_at is None


def test_mistake_report_uses_saved_recipients(
    client,
    app,
    assignment_setup,
):
    setup = assignment_setup
    assignment_id = create_assignment_for_list_test(client, setup)

    with app.app_context():
        membership = db.session.scalar(
            db.select(ClassMembership).where(
                ClassMembership.classroom_id
                == setup["classroom_id"],
                ClassMembership.student_id
                == setup["students"][0]["id"],
            )
        )
        assert membership is not None
        db.session.delete(membership)

        db.session.add(
            ClassMembership(
                classroom_id=setup["classroom_id"],
                student_id=setup["students"][2]["id"],
            )
        )
        db.session.commit()

    response = get_mistake_report(client, setup, assignment_id)

    assert response.status_code == 200
    report = response.get_json()

    assert report["summary"]["recipient_count"] == 2
    assert {
        student["student_id"]
        for student in report["students"]
    } == {
        setup["students"][0]["id"],
        setup["students"][1]["id"],
    }


@pytest.mark.parametrize(
    "status_filter",
    ["all", "not_started", "not_submitted", "submitted"],
)
def test_mistake_report_filters_participation(
    client,
    assignment_setup,
    status_filter,
):
    setup = assignment_setup
    assignment_id = create_assignment_for_list_test(client, setup)

    submit_report_attempt(
        client,
        setup,
        assignment_id,
        {"1": "A"},
    )

    response = get_mistake_report(
        client,
        setup,
        assignment_id,
        status=status_filter,
    )

    assert response.status_code == 200
    report = response.get_json()

    expected_counts = {
        "all": 2,
        "not_started": 1,
        "not_submitted": 0,
        "submitted": 1,
    }

    assert len(report["students"]) == expected_counts[status_filter]
    assert report["pagination"]["total"] == (
        expected_counts[status_filter]
    )

    # Filtering the student list must not filter class statistics.
    assert report["summary"]["recipient_count"] == 2
    assert report["questions"][0]["assessed_students"] == 1

    if status_filter != "all":
        assert all(
            student["participation_status"] == status_filter
            for student in report["students"]
        )


@pytest.mark.parametrize(
    "query",
    [
        {"page": "0"},
        {"page": "-1"},
        {"page": "abc"},
        {"page": "10001"},
        {"status": "unknown"},
    ],
)
def test_mistake_report_rejects_invalid_query(
    client,
    assignment_setup,
    query,
):
    setup = assignment_setup
    assignment_id = create_assignment_for_list_test(client, setup)

    response = get_mistake_report(
        client,
        setup,
        assignment_id,
        **query,
    )

    assert response.status_code == 400


@pytest.mark.parametrize(
    "case",
    ["draft", "invalid-questions", "question-count-mismatch"],
)
def test_mistake_report_rejects_unreliable_quiz_data(
    client,
    app,
    assignment_setup,
    case,
):
    setup = assignment_setup
    assignment_id = create_assignment_for_list_test(client, setup)

    submit_report_attempt(
        client,
        setup,
        assignment_id,
        {"1": "A"},
    )

    with app.app_context():
        quiz = db.session.get(TeacherQuiz, setup["quiz_id"])
        assert quiz is not None

        if case == "draft":
            quiz.status = "draft"
        elif case == "invalid-questions":
            quiz.questions = []
        else:
            quiz.questions = quiz.questions[:4]
            quiz.question_count = 4

        db.session.commit()

    response = get_mistake_report(client, setup, assignment_id)

    assert response.status_code == 409
    assert "questions" not in response.get_json()

def remove_assignment_for_student(client, setup, assignment_id):
    return client.patch(
        f"/api/quiz-assignments/{assignment_id}/remove",
        headers=setup["students"][0]["headers"],
        json={},
    )


def test_student_remove_moves_only_own_assignment_to_history(
    client, app, assignment_setup
):
    setup = assignment_setup
    assignment_id = create_assignment_for_list_test(client, setup)
    submit_report_attempt(
        client,
        setup,
        assignment_id,
        {"1": "A"},
    )

    response = remove_assignment_for_student(
        client, setup, assignment_id
    )
    assert response.status_code == 200

    active = client.get(
        "/api/quiz-assignments",
        headers=setup["students"][0]["headers"],
    )
    assert active.status_code == 200
    assert active.get_json()["assignments"] == []

    history = client.get(
        "/api/quiz-assignments?view=history",
        headers=setup["students"][0]["headers"],
    )
    assert history.status_code == 200
    assert [
        item["id"] for item in history.get_json()["assignments"]
    ] == [assignment_id]

    for user in (setup["students"][1], setup["teacher"]):
        response = client.get(
            "/api/quiz-assignments",
            headers=user["headers"],
        )
        assert response.status_code == 200
        assert [
            item["id"]
            for item in response.get_json()["assignments"]
        ] == [assignment_id]

    other_history = client.get(
        "/api/quiz-assignments?view=history",
        headers=setup["students"][1]["headers"],
    )
    assert other_history.status_code == 200
    assert other_history.get_json()["assignments"] == []

    with app.app_context():
        recipients = db.session.scalars(
            db.select(QuizAssignmentRecipient).where(
                QuizAssignmentRecipient.assignment_id == assignment_id
            )
        ).all()
        assert len(recipients) == 2

        for recipient in recipients:
            if recipient.student_id == setup["students"][0]["id"]:
                assert recipient.removed_at is not None
            else:
                assert recipient.removed_at is None


def test_student_remove_preserves_start_resume_and_submission(
    client, assignment_setup
):
    setup = assignment_setup
    assignment_id = create_assignment_for_list_test(client, setup)
    submit_report_attempt(
        client,
        setup,
        assignment_id,
        {"1": "A"},
    )

    response = remove_assignment_for_student(
        client, setup, assignment_id
    )
    assert response.status_code == 200

    started = start_assignment(client, setup, assignment_id)
    assert started.status_code == 201
    attempt_id = started.get_json()["attempt"]["id"]

    saved = send_attempt_answers(
        client, setup, assignment_id, attempt_id,
        answers={"1": "A"},
    )
    assert saved.status_code == 200

    resumed = start_assignment(client, setup, assignment_id)
    assert resumed.status_code == 200
    assert resumed.get_json()["attempt"]["id"] == attempt_id

    submitted = send_attempt_answers(
        client, setup, assignment_id, attempt_id,
        submit=True,
        answers={"1": "A", "2": "B"},
    )
    assert submitted.status_code == 200
    assert submitted.get_json()["result"]["score"] == 1


def test_student_remove_preserves_results_and_review_rules(
    client, app, assignment_setup
):
    setup = assignment_setup
    assignment_id, attempt_id = prepare_submitted_review(client, setup)

    response = remove_assignment_for_student(
        client, setup, assignment_id
    )
    assert response.status_code == 200

    attempts = client.get(
        f"/api/quiz-assignments/{assignment_id}/attempts",
        headers=setup["students"][0]["headers"],
    )
    assert attempts.status_code == 200
    assert attempts.get_json()["attempts"][0]["id"] == attempt_id

    # Removing does not unlock answers before the review time.
    review_path = (
        f"/api/quiz-assignments/{assignment_id}"
        f"/attempts/{attempt_id}/review"
    )
    early_review = client.get(
        review_path,
        headers=setup["students"][0]["headers"],
    )
    assert early_review.status_code in (403, 409)
    assert_no_review_answers(early_review)

    unlock_assignment_review(app, assignment_id)

    review = client.get(
        review_path,
        headers=setup["students"][0]["headers"],
    )
    assert review.status_code == 200
    assert review.get_json()["review"]["questions"]

    teacher_results = get_teacher_results(
        client, setup, assignment_id
    )
    assert teacher_results.status_code == 200

    teacher_review = get_teacher_submission_review(
        client, setup, assignment_id, attempt_id
    )
    assert teacher_review.status_code == 200


def test_student_remove_repeated_request_preserves_timestamp(
    client, app, assignment_setup
):
    setup = assignment_setup
    assignment_id = create_assignment_for_list_test(client, setup)
    submit_report_attempt(
        client,
        setup,
        assignment_id,
        {"1": "A"},
    )

    response = remove_assignment_for_student(
        client, setup, assignment_id
    )
    assert response.status_code == 200

    with app.app_context():
        recipient = db.session.scalar(
            db.select(QuizAssignmentRecipient).where(
                QuizAssignmentRecipient.assignment_id == assignment_id,
                QuizAssignmentRecipient.student_id
                == setup["students"][0]["id"],
            )
        )
        assert recipient is not None
        original_time = recipient.removed_at
        assert original_time is not None

    response = remove_assignment_for_student(
        client, setup, assignment_id
    )
    assert response.status_code == 200

    with app.app_context():
        recipient = db.session.scalar(
            db.select(QuizAssignmentRecipient).where(
                QuizAssignmentRecipient.assignment_id == assignment_id,
                QuizAssignmentRecipient.student_id
                == setup["students"][0]["id"],
            )
        )
        assert recipient is not None
        assert recipient.removed_at == original_time


@pytest.mark.parametrize(
    ("actor", "expected_status"),
    [
        ("teacher", 403),
        ("other_teacher", 403),
        ("outsider", 404),
    ],
)
def test_student_remove_rejects_unauthorized_users(
    client, app, assignment_setup, actor, expected_status
):
    setup = assignment_setup
    assignment_id = create_assignment_for_list_test(client, setup)

    user = (
        setup["students"][2]
        if actor == "outsider"
        else setup[actor]
    )

    response = client.patch(
        f"/api/quiz-assignments/{assignment_id}/remove",
        headers=user["headers"],
        json={},
    )
    assert response.status_code == expected_status

    with app.app_context():
        recipients = db.session.scalars(
            db.select(QuizAssignmentRecipient).where(
                QuizAssignmentRecipient.assignment_id == assignment_id
            )
        ).all()
        assert all(item.removed_at is None for item in recipients)


def test_student_remove_requires_authentication(client):
    response = client.patch(
        "/api/quiz-assignments/unknown/remove",
        json={},
    )
    assert response.status_code == 401


def test_student_remove_rejects_missing_assignment(
    client, assignment_setup
):
    response = remove_assignment_for_student(
        client, assignment_setup, "unknown"
    )
    assert response.status_code == 404


@pytest.mark.parametrize(
    "payload",
    [[], "remove", {"student_id": 999}],
)
def test_student_remove_rejects_invalid_body(
    client, app, assignment_setup, payload
):
    setup = assignment_setup
    assignment_id = create_assignment_for_list_test(client, setup)

    response = client.patch(
        f"/api/quiz-assignments/{assignment_id}/remove",
        headers=setup["students"][0]["headers"],
        json=payload,
    )
    assert response.status_code == 400

    with app.app_context():
        recipient = db.session.scalar(
            db.select(QuizAssignmentRecipient).where(
                QuizAssignmentRecipient.assignment_id == assignment_id,
                QuizAssignmentRecipient.student_id
                == setup["students"][0]["id"],
            )
        )
        assert recipient is not None
        assert recipient.removed_at is None


@pytest.mark.parametrize("view", ["", "all", "deleted"])
def test_student_assignment_list_rejects_invalid_view(
    client, assignment_setup, view
):
    response = client.get(
        "/api/quiz-assignments",
        headers=assignment_setup["students"][0]["headers"],
        query_string={"view": view},
    )
    assert response.status_code == 400


def test_teacher_cannot_use_student_assignment_history(
    client, assignment_setup
):
    response = client.get(
        "/api/quiz-assignments?view=history",
        headers=assignment_setup["teacher"]["headers"],
    )
    assert response.status_code == 403


def test_student_remove_database_failure_rolls_back(
    client, app, assignment_setup, monkeypatch
):
    setup = assignment_setup
    assignment_id = create_assignment_for_list_test(client, setup)
    submit_report_attempt(
        client,
        setup,
        assignment_id,
        {"1": "A"},
    )

    with monkeypatch.context() as patch:
        patch.setattr(
            db.session,
            "commit",
            Mock(side_effect=SQLAlchemyError("Test failure")),
        )
        response = remove_assignment_for_student(
            client, setup, assignment_id
        )

    assert response.status_code == 500

    with app.app_context():
        recipient = db.session.scalar(
            db.select(QuizAssignmentRecipient).where(
                QuizAssignmentRecipient.assignment_id == assignment_id,
                QuizAssignmentRecipient.student_id
                == setup["students"][0]["id"],
            )
        )
        assert recipient is not None
        assert recipient.removed_at is None

    retry = remove_assignment_for_student(
        client, setup, assignment_id
    )
    assert retry.status_code == 200

@pytest.mark.parametrize(
    "attempt_state",
    ["not_started", "in_progress", "expired", "other_student_submitted"],
)
def test_student_remove_requires_own_submitted_attempt(
    client,
    app,
    assignment_setup,
    attempt_state,
):
    setup = assignment_setup
    assignment_id = create_assignment_for_list_test(client, setup)

    if attempt_state in ("in_progress", "expired"):
        started = start_assignment(client, setup, assignment_id)
        assert started.status_code == 201
        attempt_id = started.get_json()["attempt"]["id"]

        if attempt_state == "expired":
            with app.app_context():
                attempt = db.session.get(
                    QuizAssignmentAttempt,
                    attempt_id,
                )
                assert attempt is not None

                now = datetime.now(timezone.utc)
                attempt.started_at = now - timedelta(minutes=31)
                attempt.expires_at = now - timedelta(minutes=1)
                db.session.commit()

    elif attempt_state == "other_student_submitted":
        submit_report_attempt(
            client,
            setup,
            assignment_id,
            {"1": "A"},
            student_index=1,
        )

    response = remove_assignment_for_student(
        client,
        setup,
        assignment_id,
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "SUBMITTED_ATTEMPT_REQUIRED"

    with app.app_context():
        recipient = db.session.scalar(
            db.select(QuizAssignmentRecipient).where(
                QuizAssignmentRecipient.assignment_id == assignment_id,
                QuizAssignmentRecipient.student_id
                == setup["students"][0]["id"],
            )
        )
        assert recipient is not None
        assert recipient.removed_at is None

    active = client.get(
        "/api/quiz-assignments",
        headers=setup["students"][0]["headers"],
    )
    assert active.status_code == 200
    assert [
        item["id"] for item in active.get_json()["assignments"]
    ] == [assignment_id]

    history = client.get(
        "/api/quiz-assignments?view=history",
        headers=setup["students"][0]["headers"],
    )
    assert history.status_code == 200
    assert history.get_json()["assignments"] == []