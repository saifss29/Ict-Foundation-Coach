from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from extensions import db
from models.classroom import Classroom
from models.quiz_assignment import QuizAssignment
from models.quiz_assignment_attempt import QuizAssignmentAttempt
from models.quiz_attempt import QuizAttempt
from models.teacher_quiz import TeacherQuiz
from models.topic import Topic


@pytest.fixture()
def attempt_setup(client, app):
    user_ids = {}

    for role in ("teacher", "student"):
        registration_data = {
            "name": f"Attempt {role.title()}",
            "email": f"attempt-{role}@example.com",
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
            description="Attempt model test topic.",
            display_order=1,
        )
        classroom = Classroom(
            name="Attempt Test Class",
            teacher_id=user_ids["teacher"],
            join_code="ATTEMPT1",
        )
        db.session.add_all([topic, classroom])
        db.session.flush()

        quiz = TeacherQuiz(
            teacher_id=user_ids["teacher"],
            topic_id=topic.id,
            title="Attempt Test Quiz",
            response_language="english",
            questions=[],
        )
        quiz.status = "published"
        db.session.add(quiz)
        db.session.flush()

        now = datetime.now(timezone.utc)
        assignment = QuizAssignment(
            quiz_id=quiz.id,
            classroom_id=classroom.id,
            audience="all",
            available_at=now,
            deadline_at=now + timedelta(days=1),
            time_limit_minutes=30,
            max_attempts=5,
            review_at=now + timedelta(days=1),
        )
        db.session.add(assignment)
        db.session.commit()

        return {
            "assignment_id": assignment.id,
            "student_id": user_ids["student"],
            "topic_id": topic.id,
        }

def make_attempt(setup, attempt_number=1):
    now = datetime.now(timezone.utc)

    return QuizAssignmentAttempt(
        assignment_id=setup["assignment_id"],
        student_id=setup["student_id"],
        attempt_number=attempt_number,
        started_at=now,
        expires_at=now + timedelta(minutes=30),
        total_questions=5,
    )


def test_assignment_attempt_saves_in_progress(app, attempt_setup):
    with app.app_context():
        attempt = make_attempt(attempt_setup)
        db.session.add(attempt)
        db.session.commit()
        attempt_id = attempt.id

        db.session.expire_all()
        saved = db.session.get(QuizAssignmentAttempt, attempt_id)

        assert saved is not None
        assert saved.assignment_id == attempt_setup["assignment_id"]
        assert saved.student_id == attempt_setup["student_id"]
        assert saved.attempt_number == 1
        assert saved.answers == {}
        assert saved.score is None
        assert saved.submitted_at is None
        assert saved.quiz_attempt_id is None


def test_assignment_attempt_links_completed_progress(
    app, attempt_setup
):
    with app.app_context():
        attempt = make_attempt(attempt_setup)
        progress = QuizAttempt(
            user_id=attempt_setup["student_id"],
            topic_id=attempt_setup["topic_id"],
            score=4,
            total_questions=5,
        )
        db.session.add(progress)
        db.session.flush()

        attempt.answers = {"1": "A", "2": "B"}
        attempt.score = 4
        attempt.submitted_at = attempt.started_at + timedelta(minutes=2)
        attempt.quiz_attempt_id = progress.id

        db.session.add(attempt)
        db.session.commit()
        attempt_id = attempt.id

        db.session.expire_all()
        saved = db.session.get(QuizAssignmentAttempt, attempt_id)

        assert saved is not None
        assert saved.answers == {"1": "A", "2": "B"}
        assert saved.score == 4
        assert saved.submitted_at is not None
        assert saved.quiz_attempt_id == progress.id


@pytest.mark.parametrize(
    "invalid_case",
    [
        "attempt-zero",
        "attempt-six",
        "expiry-equal",
        "expiry-before",
        "questions-zero",
        "questions-twenty-one",
        "score-negative",
        "score-too-high",
        "score-without-submission",
        "submission-without-score",
        "submission-without-progress",
        "submission-before-start",
    ],
)
def test_assignment_attempt_rejects_invalid_state(
    app, attempt_setup, invalid_case
):
    with app.app_context():
        attempt = make_attempt(attempt_setup)

        if invalid_case == "attempt-zero":
            attempt.attempt_number = 0
        elif invalid_case == "attempt-six":
            attempt.attempt_number = 6
        elif invalid_case == "expiry-equal":
            attempt.expires_at = attempt.started_at
        elif invalid_case == "expiry-before":
            attempt.expires_at = (
                attempt.started_at - timedelta(seconds=1)
            )
        elif invalid_case == "questions-zero":
            attempt.total_questions = 0
        elif invalid_case == "questions-twenty-one":
            attempt.total_questions = 21
        elif invalid_case == "score-without-submission":
            attempt.score = 3
        elif invalid_case == "submission-without-score":
            attempt.submitted_at = attempt.started_at
        elif invalid_case == "submission-without-progress":
            attempt.score = 3
            attempt.submitted_at = attempt.started_at
        else:
            # Supply a valid progress link so the intended score/time
            # constraint, rather than an incomplete submission, fails.
            progress = QuizAttempt(
                user_id=attempt_setup["student_id"],
                topic_id=attempt_setup["topic_id"],
                score=3,
                total_questions=5,
            )
            db.session.add(progress)
            db.session.flush()

            attempt.quiz_attempt_id = progress.id
            attempt.score = 3
            attempt.submitted_at = attempt.started_at

            if invalid_case == "score-negative":
                attempt.score = -1
            elif invalid_case == "score-too-high":
                attempt.score = 6
            elif invalid_case == "submission-before-start":
                attempt.submitted_at = (
                    attempt.started_at - timedelta(seconds=1)
                )

        db.session.add(attempt)

        with pytest.raises(IntegrityError):
            db.session.commit()

        db.session.rollback()

        assert db.session.scalar(
            db.select(db.func.count()).select_from(
                QuizAssignmentAttempt
            )
        ) == 0


def test_assignment_attempt_rejects_duplicate_number(
    app, attempt_setup
):
    with app.app_context():
        first = make_attempt(attempt_setup)
        db.session.add(first)
        db.session.commit()

        duplicate = make_attempt(attempt_setup)
        db.session.add(duplicate)

        with pytest.raises(IntegrityError):
            db.session.commit()

        db.session.rollback()

        assert db.session.scalar(
            db.select(db.func.count()).select_from(
                QuizAssignmentAttempt
            )
        ) == 1


def test_assignment_attempt_allows_next_number(app, attempt_setup):
    with app.app_context():
        db.session.add_all([
            make_attempt(attempt_setup, attempt_number=1),
            make_attempt(attempt_setup, attempt_number=2),
        ])
        db.session.commit()

        assert db.session.scalar(
            db.select(db.func.count()).select_from(
                QuizAssignmentAttempt
            )
        ) == 2