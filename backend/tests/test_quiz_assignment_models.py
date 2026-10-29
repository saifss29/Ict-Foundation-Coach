from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from extensions import db
from models.classroom import Classroom
from models.quiz_assignment import QuizAssignment
from models.quiz_assignment_recipient import QuizAssignmentRecipient
from models.teacher_quiz import TeacherQuiz
from models.topic import Topic


@pytest.fixture()
def assignment_records(client, app):
    user_ids = {}

    for role in ("teacher", "student"):
        registration_data = {
            "name": f"Assignment {role.title()}",
            "email": f"assignment-{role}@example.com",
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
        user_ids[role] = response.get_json()["user"]["id"]

    with app.app_context():
        topic = Topic(
            title="Number Systems",
            slug="number-systems",
            description="Verified ICT practice topic.",
            display_order=1,
        )
        classroom = Classroom(
            name="Assignment Test Class",
            teacher_id=user_ids["teacher"],
            join_code="TEST1234",
        )

        db.session.add_all([topic, classroom])
        db.session.flush()

        quiz = TeacherQuiz(
            teacher_id=user_ids["teacher"],
            topic_id=topic.id,
            title="Assignment Practice Quiz",
            response_language="english",
            questions=[
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
                for index in range(1, 6)
            ],
        )

        quiz.status = "published"
        quiz.published_at = datetime.now(timezone.utc)

        db.session.add(quiz)
        db.session.commit()

        return {
            "quiz_id": quiz.id,
            "classroom_id": classroom.id,
            "student_id": user_ids["student"],
        }

def assignment_values(records):
    available_at = datetime.now(timezone.utc)

    return {
        "quiz_id": records["quiz_id"],
        "classroom_id": records["classroom_id"],
        "audience": "all",
        "available_at": available_at,
        "deadline_at": available_at + timedelta(days=1),
        "time_limit_minutes": 30,
        "review_at": available_at + timedelta(days=1),
        "max_attempts": 1,
    }


@pytest.mark.parametrize("audience", ["all", "selected"])
def test_assignment_and_recipient_are_saved(
    app,
    assignment_records,
    audience,
):
    values = assignment_values(assignment_records)
    values["audience"] = audience

    with app.app_context():
        assignment = QuizAssignment(**values)
        db.session.add(assignment)
        db.session.flush()

        recipient = QuizAssignmentRecipient(
            assignment_id=assignment.id,
            student_id=assignment_records["student_id"],
        )
        db.session.add(recipient)
        db.session.commit()

        assignment_id = assignment.id
        recipient_id = recipient.id
        db.session.remove()

        saved = db.session.get(QuizAssignment, assignment_id)
        saved_recipient = db.session.get(
            QuizAssignmentRecipient,
            recipient_id,
        )

        assert saved is not None
        assert saved.quiz_id == assignment_records["quiz_id"]
        assert saved.classroom_id == assignment_records["classroom_id"]
        assert saved.audience == audience
        assert saved.time_limit_minutes == 30
        assert saved.max_attempts == 1
        assert saved.created_at is not None

        assert saved_recipient is not None
        assert saved_recipient.assignment_id == assignment_id
        assert saved_recipient.student_id == assignment_records["student_id"]
        assert saved_recipient.created_at is not None


@pytest.mark.parametrize(
    ("time_limit", "attempts"),
    [(1, 1), (180, 5)],
)
def test_assignment_accepts_limit_boundaries(
    app,
    assignment_records,
    time_limit,
    attempts,
):
    values = assignment_values(assignment_records)
    values["time_limit_minutes"] = time_limit
    values["max_attempts"] = attempts

    with app.app_context():
        assignment = QuizAssignment(**values)
        db.session.add(assignment)
        db.session.commit()

        assert assignment.time_limit_minutes == time_limit
        assert assignment.max_attempts == attempts


@pytest.mark.parametrize(
    "invalid_case",
    [
        "invalid-audience",
        "equal-deadline",
        "earlier-deadline",
        "early-review",
        "zero-time-limit",
        "excessive-time-limit",
        "zero-attempts",
        "excessive-attempts",
    ],
)
def test_database_rejects_invalid_assignment_settings(
    app,
    assignment_records,
    invalid_case,
):
    values = assignment_values(assignment_records)

    if invalid_case == "invalid-audience":
        values["audience"] = "everyone"
    elif invalid_case == "equal-deadline":
        values["deadline_at"] = values["available_at"]
    elif invalid_case == "earlier-deadline":
        values["deadline_at"] = (
            values["available_at"] - timedelta(minutes=1)
        )
    elif invalid_case == "early-review":
        values["review_at"] = (
            values["deadline_at"] - timedelta(minutes=1)
        )
    elif invalid_case == "zero-time-limit":
        values["time_limit_minutes"] = 0
    elif invalid_case == "excessive-time-limit":
        values["time_limit_minutes"] = 181
    elif invalid_case == "zero-attempts":
        values["max_attempts"] = 0
    elif invalid_case == "excessive-attempts":
        values["max_attempts"] = 6

    with app.app_context():
        db.session.add(QuizAssignment(**values))

        with pytest.raises(IntegrityError):
            db.session.commit()

        db.session.rollback()

        assert db.session.scalar(
            db.select(db.func.count()).select_from(QuizAssignment)
        ) == 0

        # Verify the session remains usable after rollback.
        db.session.add(
            QuizAssignment(**assignment_values(assignment_records))
        )
        db.session.commit()

        assert db.session.scalar(
            db.select(db.func.count()).select_from(QuizAssignment)
        ) == 1


def test_database_rejects_duplicate_assignment_recipient(
    app,
    assignment_records,
):
    with app.app_context():
        assignment = QuizAssignment(
            **assignment_values(assignment_records)
        )
        db.session.add(assignment)
        db.session.flush()

        assignment_id = assignment.id
        student_id = assignment_records["student_id"]

        db.session.add(
            QuizAssignmentRecipient(
                assignment_id=assignment_id,
                student_id=student_id,
            )
        )
        db.session.commit()

        db.session.add(
            QuizAssignmentRecipient(
                assignment_id=assignment_id,
                student_id=student_id,
            )
        )

        with pytest.raises(IntegrityError):
            db.session.commit()

        db.session.rollback()

        assert db.session.scalar(
            db.select(db.func.count()).select_from(
                QuizAssignmentRecipient
            )
        ) == 1

        assert db.session.get(
            QuizAssignment,
            assignment_id,
        ) is not None


def test_student_can_receive_two_different_assignments(
    app,
    assignment_records,
):
    with app.app_context():
        assignments = [
            QuizAssignment(**assignment_values(assignment_records))
            for _ in range(2)
        ]

        db.session.add_all(assignments)
        db.session.flush()

        for assignment in assignments:
            db.session.add(
                QuizAssignmentRecipient(
                    assignment_id=assignment.id,
                    student_id=assignment_records["student_id"],
                )
            )

        db.session.commit()

        assert db.session.scalar(
            db.select(db.func.count()).select_from(
                QuizAssignmentRecipient
            )
        ) == 2