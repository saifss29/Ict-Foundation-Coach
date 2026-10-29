from datetime import datetime, timedelta, timezone

import pytest

from extensions import db
from models.class_membership import ClassMembership
from models.classroom import Classroom
from models.learning_assignment import LearningAssignment
from models.learning_assignment_recipient import LearningAssignmentRecipient
from models.learning_assignment_submission import LearningAssignmentSubmission
from models.notification import Notification
from models.user import User
from unittest.mock import Mock

from services.learning_feedback_service import LearningFeedbackError

BASE_URL = "/api/learning-assignments"


def login_as(client, app, role, email):
    payload = {
        "name": f"Learning {role.title()}",
        "email": email,
        "password": "SecurePass123!",
        "role": role,
    }

    if role == "student":
        payload["academic_level"] = "ssc"

    response = client.post("/api/auth/register", json=payload)
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
            ),
        },
    }


@pytest.fixture()
def setup(client, app):
    teacher = login_as(
        client, app, "teacher", "learning-owner@example.com"
    )
    other_teacher = login_as(
        client, app, "teacher", "learning-other@example.com"
    )
    students = [
        login_as(
            client,
            app,
            "student",
            f"learning-student-{index}@example.com",
        )
        for index in range(3)
    ]

    with app.app_context():
        classroom = Classroom(
            name="ICT Learning Class",
            teacher_id=teacher["id"],
            join_code="LEARN01",
        )
        other_classroom = Classroom(
            name="Other Learning Class",
            teacher_id=other_teacher["id"],
            join_code="LEARN02",
        )
        db.session.add_all([classroom, other_classroom])
        db.session.flush()

        classroom_id = classroom.id
        other_classroom_id = other_classroom.id

        for student in students[:2]:
            db.session.add(
                ClassMembership(
                    classroom_id=classroom_id,
                    student_id=student["id"],
                )
            )

        db.session.commit()

    return {
        "teacher": teacher,
        "other_teacher": other_teacher,
        "students": students,
        "classroom_id": classroom_id,
        "other_classroom_id": other_classroom_id,
    }


def assignment_payload(setup, **changes):
    now = datetime.now(timezone.utc)

    payload = {
        "classroom_id": setup["classroom_id"],
        "title": "HTML Practice",
        "instructions": "Create a heading and explain its purpose.",
        "task_type": "practical",
        "audience": "all",
        "total_marks": "10.00",
        "available_at": (now - timedelta(minutes=5)).isoformat(),
        "deadline_at": (now + timedelta(days=1)).isoformat(),
    }
    payload.update(changes)
    return payload


def create_assignment(client, setup, **changes):
    response = client.post(
        BASE_URL,
        headers=setup["teacher"]["headers"],
        json=assignment_payload(setup, **changes),
    )
    assert response.status_code == 201, response.get_json()
    return response.get_json()["assignment"]["id"]


def submit_answer(client, setup, assignment_id, **changes):
    payload = {"answer_text": "A heading identifies the topic."}
    payload.update(changes)

    return client.post(
        f"{BASE_URL}/{assignment_id}/submit",
        headers=setup["students"][0]["headers"],
        json=payload,
    )


def record_count(model):
    return db.session.scalar(
        db.select(db.func.count()).select_from(model)
    )


def test_requires_authentication(client):
    assert client.get(BASE_URL).status_code == 401
    assert client.post(BASE_URL, json={}).status_code == 401


@pytest.mark.parametrize("task_type", ["written", "practical"])
def test_teacher_creates_task_for_all_members(
    client, app, setup, task_type
):
    assignment_id = create_assignment(
        client, setup, task_type=task_type
    )

    with app.app_context():
        assignment = db.session.get(
            LearningAssignment, assignment_id
        )
        assert assignment is not None
        assert assignment.task_type == task_type
        assert record_count(LearningAssignmentRecipient) == 2

        notifications = db.session.scalars(
            db.select(Notification).where(
                Notification.notification_type == "learning_assignment"
            )
        ).all()

        assert len(notifications) == 2
        assert {item.user_id for item in notifications} == {
            student["id"] for student in setup["students"][:2]
        }


def test_student_cannot_create_task(client, setup):
    response = client.post(
        BASE_URL,
        headers=setup["students"][0]["headers"],
        json=assignment_payload(setup),
    )
    assert response.status_code == 403


def test_teacher_cannot_use_another_teachers_class(client, setup):
    response = client.post(
        BASE_URL,
        headers=setup["teacher"]["headers"],
        json=assignment_payload(
            setup,
            classroom_id=setup["other_classroom_id"],
        ),
    )
    assert response.status_code == 404


def test_selected_audience_gets_only_selected_student(
    client, app, setup
):
    assignment_id = create_assignment(
        client,
        setup,
        audience="selected",
        student_ids=[setup["students"][0]["id"]],
    )

    with app.app_context():
        recipients = db.session.scalars(
            db.select(LearningAssignmentRecipient).where(
                LearningAssignmentRecipient.assignment_id == assignment_id
            )
        ).all()

        assert len(recipients) == 1
        assert recipients[0].student_id == setup["students"][0]["id"]

    response = client.get(
        f"{BASE_URL}/{assignment_id}",
        headers=setup["students"][1]["headers"],
    )
    assert response.status_code == 404


def test_selected_outsider_is_rejected_without_records(
    client, app, setup
):
    response = client.post(
        BASE_URL,
        headers=setup["teacher"]["headers"],
        json=assignment_payload(
            setup,
            audience="selected",
            student_ids=[setup["students"][2]["id"]],
        ),
    )
    assert response.status_code == 400

    with app.app_context():
        assert record_count(LearningAssignment) == 0
        assert record_count(LearningAssignmentRecipient) == 0
        assert record_count(Notification) == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"task_type": "mcq"},
        {"title": " "},
        {"instructions": " "},
        {"total_marks": "0"},
        {"total_marks": "-1"},
        {"total_marks": "1.234"},
        {"total_marks": "NaN"},
        {"audience": "selected", "student_ids": []},
        {"audience": "all", "student_ids": [1]},
        {"unexpected_field": "value"},
    ],
)
def test_invalid_create_payload_is_rejected(
    client, app, setup, changes
):
    response = client.post(
        BASE_URL,
        headers=setup["teacher"]["headers"],
        json=assignment_payload(setup, **changes),
    )
    assert response.status_code == 400

    with app.app_context():
        assert record_count(LearningAssignment) == 0
        assert record_count(LearningAssignmentRecipient) == 0


def test_student_can_reload_task_and_submit_code(
    client, app, setup
):
    assignment_id = create_assignment(client, setup)
    code = "    print('Hello')\n"

    response = client.get(
        f"{BASE_URL}/{assignment_id}",
        headers=setup["students"][0]["headers"],
    )
    assert response.status_code == 200
    assert response.get_json()["can_submit"] is True

    response = submit_answer(
        client,
        setup,
        assignment_id,
        answer_text="",
        code_text=code,
    )
    assert response.status_code == 201, response.get_json()

    response = client.get(
        f"{BASE_URL}/{assignment_id}",
        headers=setup["students"][0]["headers"],
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["can_submit"] is False
    assert body["submission"]["code_text"] == code

    with app.app_context():
        assert record_count(LearningAssignmentSubmission) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"answer_text": "   ", "code_text": "\n"},
        {"answer_text": "Answer", "student_id": 999},
        {"answer_text": "Answer", "obtained_marks": "10"},
    ],
)
def test_invalid_submission_is_rejected(
    client, app, setup, payload
):
    assignment_id = create_assignment(client, setup)

    response = client.post(
        f"{BASE_URL}/{assignment_id}/submit",
        headers=setup["students"][0]["headers"],
        json=payload,
    )
    assert response.status_code == 400

    with app.app_context():
        assert record_count(LearningAssignmentSubmission) == 0


def test_duplicate_submission_is_rejected(client, app, setup):
    assignment_id = create_assignment(client, setup)

    assert submit_answer(
        client, setup, assignment_id
    ).status_code == 201
    assert submit_answer(
        client, setup, assignment_id
    ).status_code == 409

    with app.app_context():
        assert record_count(LearningAssignmentSubmission) == 1


def test_outsider_cannot_read_or_submit(client, setup):
    assignment_id = create_assignment(client, setup)
    headers = setup["students"][2]["headers"]

    assert client.get(
        f"{BASE_URL}/{assignment_id}",
        headers=headers,
    ).status_code == 404

    assert client.post(
        f"{BASE_URL}/{assignment_id}/submit",
        headers=headers,
        json={"answer_text": "Outsider answer"},
    ).status_code == 404


@pytest.mark.parametrize("time_state", ["future", "expired"])
def test_submission_respects_available_and_deadline(
    client, app, setup, time_state
):
    assignment_id = create_assignment(client, setup)
    now = datetime.now(timezone.utc)

    with app.app_context():
        assignment = db.session.get(
            LearningAssignment, assignment_id
        )
        assert assignment is not None

        if time_state == "future":
            assignment.available_at = now + timedelta(hours=1)
            assignment.deadline_at = now + timedelta(hours=2)
        else:
            assignment.available_at = now - timedelta(hours=2)
            assignment.deadline_at = now - timedelta(hours=1)

        db.session.commit()

    response = submit_answer(client, setup, assignment_id)
    assert response.status_code == 409

    with app.app_context():
        assert record_count(LearningAssignmentSubmission) == 0


def test_other_teacher_cannot_read_task_or_submissions(client, setup):
    assignment_id = create_assignment(client, setup)
    headers = setup["other_teacher"]["headers"]

    assert client.get(
        f"{BASE_URL}/{assignment_id}",
        headers=headers,
    ).status_code == 404

    assert client.get(
        f"{BASE_URL}/{assignment_id}/submissions",
        headers=headers,
    ).status_code == 404


@pytest.mark.parametrize("marks", ["0", "8.50", "10"])
def test_teacher_reviews_and_student_receives_feedback(
    client, app, setup, marks
):
    assignment_id = create_assignment(client, setup)
    response = submit_answer(client, setup, assignment_id)
    assert response.status_code == 201
    submission_id = response.get_json()["submission"]["id"]

    response = client.patch(
        f"{BASE_URL}/{assignment_id}/submissions/{submission_id}/review",
        headers=setup["teacher"]["headers"],
        json={
            "obtained_marks": marks,
            "feedback": "Your explanation is clear.",
        },
    )
    assert response.status_code == 200, response.get_json()

    response = client.get(
        f"{BASE_URL}/{assignment_id}",
        headers=setup["students"][0]["headers"],
    )
    submission = response.get_json()["submission"]
    assert submission["status"] == "reviewed"
    assert submission["feedback"] == "Your explanation is clear."
    assert float(submission["obtained_marks"]) == float(marks)

    with app.app_context():
        notifications = db.session.scalars(
            db.select(Notification).where(
                Notification.notification_type == "learning_assignment_review"
            )
        ).all()
        assert len(notifications) == 1
        assert notifications[0].user_id == setup["students"][0]["id"]


def test_review_above_total_marks_is_rejected(client, app, setup):
    assignment_id = create_assignment(client, setup)
    response = submit_answer(client, setup, assignment_id)
    submission_id = response.get_json()["submission"]["id"]

    response = client.patch(
        f"{BASE_URL}/{assignment_id}/submissions/{submission_id}/review",
        headers=setup["teacher"]["headers"],
        json={"obtained_marks": "10.01"},
    )
    assert response.status_code == 400

    with app.app_context():
        submission = db.session.get(
            LearningAssignmentSubmission, submission_id
        )
        assert submission is not None
        assert submission.reviewed_at is None
        assert submission.obtained_marks is None


def test_other_teacher_cannot_review_submission(client, setup):
    assignment_id = create_assignment(client, setup)
    response = submit_answer(client, setup, assignment_id)
    submission_id = response.get_json()["submission"]["id"]

    response = client.patch(
        f"{BASE_URL}/{assignment_id}/submissions/{submission_id}/review",
        headers=setup["other_teacher"]["headers"],
        json={"obtained_marks": "5"},
    )
    assert response.status_code == 404


def test_student_cannot_access_teacher_submission_list(client, setup):
    assignment_id = create_assignment(client, setup)

    response = client.get(
        f"{BASE_URL}/{assignment_id}/submissions",
        headers=setup["students"][0]["headers"],
    )
    assert response.status_code == 403


def test_duplicate_review_does_not_send_duplicate_notification(
    client, app, setup
):
    assignment_id = create_assignment(client, setup)
    response = submit_answer(client, setup, assignment_id)
    submission_id = response.get_json()["submission"]["id"]
    url = (
        f"{BASE_URL}/{assignment_id}/submissions/"
        f"{submission_id}/review"
    )

    assert client.patch(
        url,
        headers=setup["teacher"]["headers"],
        json={"obtained_marks": "5"},
    ).status_code == 200

    assert client.patch(
        url,
        headers=setup["teacher"]["headers"],
        json={"obtained_marks": "6"},
    ).status_code == 409

    with app.app_context():
        count = db.session.scalar(
            db.select(db.func.count())
            .select_from(Notification)
            .where(
                Notification.notification_type
                == "learning_assignment_review"
            )
        )
        assert count == 1


def test_assignment_list_is_scoped_to_user(client, setup):
    create_assignment(client, setup)

    for user, expected_count in [
        (setup["teacher"], 1),
        (setup["other_teacher"], 0),
        (setup["students"][0], 1),
        (setup["students"][2], 0),
    ]:
        response = client.get(
            BASE_URL,
            headers=user["headers"],
        )
        assert response.status_code == 200
        assert len(response.get_json()["assignments"]) == expected_count

AI_REFERENCE = (
    "A heading identifies the topic and helps organise the document."
)

AI_DRAFT = {
    "summary": "The answer is partly complete.",
    "strengths": ["Correctly explains that a heading identifies the topic."],
    "missing_points": ["Does not mention organising the document."],
    "improvement_suggestions": [
        "Explain how headings help organise the document."
    ],
}


@pytest.fixture()
def feedback_mock(monkeypatch):
    mock = Mock(return_value=AI_DRAFT)

    monkeypatch.setattr(
        "routes.learning_assignments.generate_learning_feedback",
        mock,
    )

    return mock


def create_feedback_submission(client, setup, **changes):
    payload = {
        "task_type": "written",
        "reference_answer": AI_REFERENCE,
    }
    payload.update(changes)

    assignment_id = create_assignment(client, setup, **payload)
    response = submit_answer(client, setup, assignment_id)

    assert response.status_code == 201, response.get_json()

    submission_id = response.get_json()["submission"]["id"]

    return assignment_id, submission_id


def feedback_url(assignment_id, submission_id):
    return (
        f"{BASE_URL}/{assignment_id}/submissions/"
        f"{submission_id}/ai-feedback"
    )


def test_ai_feedback_saves_reloads_and_preserves_manual_review(
    client, app, setup, feedback_mock
):
    assignment_id, submission_id = create_feedback_submission(
        client, setup
    )

    with app.app_context():
        notification_count = record_count(Notification)

        assignment = db.session.get(LearningAssignment, assignment_id)
        assert assignment is not None
        assert assignment.reference_answer == AI_REFERENCE

    response = client.post(
        feedback_url(assignment_id, submission_id),
        headers=setup["teacher"]["headers"],
        json={"response_language": "english"},
    )

    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert body["ai_feedback"] == AI_DRAFT
    assert body["ai_feedback_generated_at"] is not None
    assert body["cached"] is False

    feedback_mock.assert_called_once_with(
        title="HTML Practice",
        instructions="Create a heading and explain its purpose.",
        reference_answer=AI_REFERENCE,
        answer_text="A heading identifies the topic.",
        response_language="english",
    )

    with app.app_context():
        submission = db.session.get(
            LearningAssignmentSubmission, submission_id
        )
        submission = db.session.get(
            LearningAssignmentSubmission, submission_id
        )
        assert submission is not None

        assert submission.ai_feedback == AI_DRAFT
        assert submission.ai_feedback_generated_at is not None
        assert submission.obtained_marks is None
        assert submission.reviewed_at is None
        assert submission.reviewed_by is None
        assert submission.feedback == ""
        assert record_count(Notification) == notification_count

    response = client.get(
        f"{BASE_URL}/{assignment_id}/submissions",
        headers=setup["teacher"]["headers"],
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["assignment"]["reference_answer"] == AI_REFERENCE

    student_row = next(
        item
        for item in body["students"]
        if item["student_id"] == setup["students"][0]["id"]
    )
    assert student_row["submission"]["ai_feedback"] == AI_DRAFT
    assert student_row["submission"]["status"] == "submitted"

    # Repeated requests reuse the saved draft.
    response = client.post(
        feedback_url(assignment_id, submission_id),
        headers=setup["teacher"]["headers"],
        json={"response_language": "english"},
    )

    assert response.status_code == 200
    assert response.get_json()["cached"] is True
    assert response.get_json()["ai_feedback"] == AI_DRAFT
    feedback_mock.assert_called_once()

    # Teacher can still give independent final marks and feedback.
    response = client.patch(
        f"{BASE_URL}/{assignment_id}/submissions/{submission_id}/review",
        headers=setup["teacher"]["headers"],
        json={
            "obtained_marks": "7.50",
            "feedback": "Teacher final feedback.",
        },
    )

    assert response.status_code == 200, response.get_json()

    response = client.get(
        f"{BASE_URL}/{assignment_id}",
        headers=setup["students"][0]["headers"],
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["submission"]["status"] == "reviewed"
    assert float(body["submission"]["obtained_marks"]) == 7.5
    assert body["submission"]["feedback"] == "Teacher final feedback."
    assert "reference_answer" not in body["assignment"]
    assert "ai_feedback" not in body["submission"]
    assert "ai_feedback_generated_at" not in body["submission"]


def test_student_cannot_read_reference_or_ai_draft_before_review(
    client, setup, feedback_mock
):
    assignment_id, submission_id = create_feedback_submission(
        client, setup
    )

    assert client.post(
        feedback_url(assignment_id, submission_id),
        headers=setup["teacher"]["headers"],
        json={},
    ).status_code == 200

    response = client.get(
        BASE_URL,
        headers=setup["students"][0]["headers"],
    )

    assert response.status_code == 200
    for assignment in response.get_json()["assignments"]:
        assert "reference_answer" not in assignment

    response = client.get(
        f"{BASE_URL}/{assignment_id}",
        headers=setup["students"][0]["headers"],
    )

    assert response.status_code == 200
    body = response.get_json()
    assert "reference_answer" not in body["assignment"]
    assert "ai_feedback" not in body["submission"]
    assert "ai_feedback_generated_at" not in body["submission"]
    assert body["submission"]["status"] == "submitted"
    assert body["submission"]["feedback"] == ""


@pytest.mark.parametrize(
    ("actor", "expected_status"),
    [
        ("anonymous", 401),
        ("student", 403),
        ("other_teacher", 404),
    ],
)
def test_ai_feedback_requires_owning_teacher(
    client, setup, feedback_mock, actor, expected_status
):
    assignment_id, submission_id = create_feedback_submission(
        client, setup
    )

    headers = {}
    if actor == "student":
        headers = setup["students"][0]["headers"]
    elif actor == "other_teacher":
        headers = setup["other_teacher"]["headers"]

    response = client.post(
        feedback_url(assignment_id, submission_id),
        headers=headers,
        json={},
    )

    assert response.status_code == expected_status
    feedback_mock.assert_not_called()


@pytest.mark.parametrize(
    "payload",
    [
        [],
        "invalid",
        {"response_language": None},
        {"response_language": True},
        {"response_language": "french"},
        {"response_language": " "},
        {"obtained_marks": "10"},
        {"student_id": 1},
    ],
)
def test_ai_feedback_rejects_invalid_body(
    client, setup, feedback_mock, payload
):
    assignment_id, submission_id = create_feedback_submission(
        client, setup
    )

    response = client.post(
        feedback_url(assignment_id, submission_id),
        headers=setup["teacher"]["headers"],
        json=payload,
    )

    assert response.status_code == 400
    feedback_mock.assert_not_called()


def test_ai_feedback_rejects_missing_json(
    client, setup, feedback_mock
):
    assignment_id, submission_id = create_feedback_submission(
        client, setup
    )

    response = client.post(
        feedback_url(assignment_id, submission_id),
        headers=setup["teacher"]["headers"],
    )

    assert response.status_code == 400
    feedback_mock.assert_not_called()


@pytest.mark.parametrize(
    "changes",
    [
        {"task_type": "practical"},
        {"reference_answer": ""},
        {"reference_answer": "   "},
    ],
)
def test_ai_feedback_requires_written_task_and_reference(
    client, setup, feedback_mock, changes
):
    assignment_id, submission_id = create_feedback_submission(
        client, setup, **changes
    )

    response = client.post(
        feedback_url(assignment_id, submission_id),
        headers=setup["teacher"]["headers"],
        json={},
    )

    assert response.status_code == 400
    feedback_mock.assert_not_called()


def test_ai_feedback_rejects_code_only_submission(
    client, setup, feedback_mock
):
    assignment_id = create_assignment(
        client,
        setup,
        task_type="written",
        reference_answer=AI_REFERENCE,
    )

    response = submit_answer(
        client,
        setup,
        assignment_id,
        answer_text="",
        code_text="print('Hello')",
    )

    assert response.status_code == 201
    submission_id = response.get_json()["submission"]["id"]

    response = client.post(
        feedback_url(assignment_id, submission_id),
        headers=setup["teacher"]["headers"],
        json={},
    )

    assert response.status_code == 400
    feedback_mock.assert_not_called()


def test_ai_feedback_cannot_use_submission_from_another_assignment(
    client, setup, feedback_mock
):
    assignment_id, submission_id = create_feedback_submission(
        client, setup
    )
    other_assignment_id = create_assignment(
        client,
        setup,
        task_type="written",
        reference_answer=AI_REFERENCE,
    )

    assert assignment_id != other_assignment_id

    response = client.post(
        feedback_url(other_assignment_id, submission_id),
        headers=setup["teacher"]["headers"],
        json={},
    )

    assert response.status_code == 404
    feedback_mock.assert_not_called()


def test_ai_feedback_does_not_generate_after_final_review(
    client, setup, feedback_mock
):
    assignment_id, submission_id = create_feedback_submission(
        client, setup
    )

    response = client.patch(
        f"{BASE_URL}/{assignment_id}/submissions/{submission_id}/review",
        headers=setup["teacher"]["headers"],
        json={"obtained_marks": "5", "feedback": "Final review."},
    )
    assert response.status_code == 200

    response = client.post(
        feedback_url(assignment_id, submission_id),
        headers=setup["teacher"]["headers"],
        json={},
    )

    assert response.status_code == 409
    feedback_mock.assert_not_called()


@pytest.mark.parametrize("status_code", [500, 502, 504])
def test_ai_feedback_failure_does_not_change_submission(
    client, app, setup, feedback_mock, status_code
):
    assignment_id, submission_id = create_feedback_submission(
        client, setup
    )

    feedback_mock.side_effect = LearningFeedbackError(
        "Feedback service unavailable.",
        status_code,
    )

    with app.app_context():
        notification_count = record_count(Notification)

    response = client.post(
        feedback_url(assignment_id, submission_id),
        headers=setup["teacher"]["headers"],
        json={},
    )

    assert response.status_code == status_code
    assert response.get_json()["error"] == "Feedback service unavailable."

    with app.app_context():
        submission = db.session.get(
            LearningAssignmentSubmission, submission_id
        )
        submission = db.session.get(
            LearningAssignmentSubmission, submission_id
        )
        assert submission is not None
        assert submission.ai_feedback is None
        assert submission.ai_feedback_generated_at is None
        assert submission.obtained_marks is None
        assert submission.reviewed_at is None
        assert submission.reviewed_by is None
        assert submission.feedback == ""
        assert record_count(Notification) == notification_count

    # Manual review remains available after an AI failure.
    response = client.patch(
        f"{BASE_URL}/{assignment_id}/submissions/{submission_id}/review",
        headers=setup["teacher"]["headers"],
        json={"obtained_marks": "6", "feedback": "Manual feedback."},
    )

    assert response.status_code == 200


def test_ai_feedback_discards_draft_if_teacher_reviews_during_call(
    client, app, setup, feedback_mock
):
    assignment_id, submission_id = create_feedback_submission(
        client, setup
    )

    def review_during_generation(**kwargs):
        with app.app_context():
            submission = db.session.get(
                LearningAssignmentSubmission, submission_id
            )
            assert submission is not None

            submission.obtained_marks = 8
            submission.feedback = "Already reviewed by teacher."
            submission.reviewed_by = setup["teacher"]["id"]
            submission.reviewed_at = datetime.now(timezone.utc)

            db.session.commit()

        return AI_DRAFT

    feedback_mock.side_effect = review_during_generation

    response = client.post(
        feedback_url(assignment_id, submission_id),
        headers=setup["teacher"]["headers"],
        json={},
    )

    assert response.status_code == 409

    with app.app_context():
        submission = db.session.get(
            LearningAssignmentSubmission, submission_id
        )
        assert submission is not None

        assert submission.ai_feedback is None
        assert submission.ai_feedback_generated_at is None
        assert float(submission.obtained_marks) == 8
        assert submission.feedback == "Already reviewed by teacher."
        assert submission.reviewed_by == setup["teacher"]["id"]
        assert submission.reviewed_at is not None


def test_ai_feedback_discards_draft_if_reference_changes_during_call(
    client, app, setup, feedback_mock
):
    assignment_id, submission_id = create_feedback_submission(
        client, setup
    )

    def change_reference_during_generation(**kwargs):
        with app.app_context():
            assignment = db.session.get(
                LearningAssignment, assignment_id
            )
            assert assignment is not None

            assignment.reference_answer = "Updated teacher reference."
            db.session.commit()

        return AI_DRAFT
    feedback_mock.side_effect = change_reference_during_generation

    response = client.post(
        feedback_url(assignment_id, submission_id),
        headers=setup["teacher"]["headers"],
        json={},
    )

    assert response.status_code == 409

    with app.app_context():
        submission = db.session.get(
            LearningAssignmentSubmission, submission_id
        )
        submission = db.session.get(
            LearningAssignmentSubmission, submission_id
        )
        assert submission is not None
        assert submission.ai_feedback is None
        assert submission.ai_feedback_generated_at is None


@pytest.fixture()
def reference_mock(monkeypatch):
    mock = Mock(
        return_value="Save stores changes to the current document."
    )
    monkeypatch.setattr(
        "routes.learning_assignments.generate_reference_answer",
        mock,
    )
    return mock


@pytest.mark.parametrize("academic_level", ["ssc", "hsc"])
@pytest.mark.parametrize("response_language", ["banglish", "english"])
def test_teacher_generates_reference_draft_without_creating_assignment(
    client,
    setup,
    reference_mock,
    academic_level,
    response_language,
):
    before = record_count(LearningAssignment)

    response = client.post(
        "/api/learning-assignments/reference-answer",
        headers=setup["teacher"]["headers"],
        json={
            "title": " Save and Save As ",
            "instructions": " Explain the difference. ",
            "academic_level": academic_level,
            "response_language": response_language,
        },
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "reference_answer": (
            "Save stores changes to the current document."
        ),
        "is_draft": True,
    }

    reference_mock.assert_called_once_with(
        title="Save and Save As",
        instructions="Explain the difference.",
        academic_level=academic_level,
        response_language=response_language,
    )

    assert record_count(LearningAssignment) == before


def test_reference_generation_requires_authentication(
    client,
    reference_mock,
):
    response = client.post(
        "/api/learning-assignments/reference-answer",
        json={},
    )

    assert response.status_code == 401
    reference_mock.assert_not_called()


def test_student_cannot_generate_teacher_reference(
    client,
    setup,
    reference_mock,
):
    response = client.post(
        "/api/learning-assignments/reference-answer",
        headers=setup["students"][0]["headers"],
        json={
            "title": "Save and Save As",
            "instructions": "Explain the difference.",
            "academic_level": "ssc",
        },
    )

    assert response.status_code == 403
    reference_mock.assert_not_called()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", None),
        ("title", "  "),
        ("title", "a" * 151),
        ("instructions", None),
        ("instructions", "   "),
        ("instructions", "a" * 10001),
        ("academic_level", "university"),
        ("academic_level", []),
        ("response_language", "unknown"),
        ("response_language", {}),
        ("student_id", 1),
    ],
)
def test_reference_generation_rejects_invalid_input_before_maira(
    client,
    setup,
    reference_mock,
    field,
    value,
):
    payload = {
        "title": "Save and Save As",
        "instructions": "Explain the difference.",
        "academic_level": "ssc",
    }
    payload[field] = value

    response = client.post(
        "/api/learning-assignments/reference-answer",
        headers=setup["teacher"]["headers"],
        json=payload,
    )

    assert response.status_code == 400
    reference_mock.assert_not_called()


def test_reference_generation_rejects_missing_json(
    client,
    setup,
    reference_mock,
):
    response = client.post(
        "/api/learning-assignments/reference-answer",
        headers=setup["teacher"]["headers"],
    )

    assert response.status_code == 400
    reference_mock.assert_not_called()


def test_reference_generation_defaults_to_banglish(
    client,
    setup,
    reference_mock,
):
    response = client.post(
        "/api/learning-assignments/reference-answer",
        headers=setup["teacher"]["headers"],
        json={
            "title": "Save and Save As",
            "instructions": "Explain the difference.",
            "academic_level": "ssc",
        },
    )

    assert response.status_code == 200
    assert (
        reference_mock.call_args.kwargs["response_language"]
        == "banglish"
    )


@pytest.mark.parametrize("status_code", [422, 500, 502, 504])
def test_reference_generation_returns_service_error_without_creating_assignment(
    client,
    setup,
    reference_mock,
    status_code,
):
    from services.learning_reference_service import (
        LearningReferenceError,
    )

    before = record_count(LearningAssignment)
    reference_mock.side_effect = LearningReferenceError(
        "Reference generation failed.",
        status_code,
    )

    response = client.post(
        "/api/learning-assignments/reference-answer",
        headers=setup["teacher"]["headers"],
        json={
            "title": "Save and Save As",
            "instructions": "Explain the difference.",
            "academic_level": "ssc",
        },
    )

    assert response.status_code == status_code
    assert (
        response.get_json()["error"]
        == "Reference generation failed."
    )
    assert record_count(LearningAssignment) == before