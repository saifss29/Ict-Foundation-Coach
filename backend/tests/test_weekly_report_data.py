from datetime import datetime, timedelta, timezone

import pytest

from extensions import db
from services.weekly_report_data_service import (
    collect_weekly_report_data,
)


REPORT_END = datetime(2026, 10, 12, 6, 0, tzinfo=timezone.utc)
REPORT_START = REPORT_END - timedelta(days=7)


def create_student():
    users = db.metadata.tables["users"]

    return db.session.execute(
        users.insert().values(
            name="Report Student",
            email="report-student@example.com",
            password_hash="test-only",
            role="student",
            academic_level="ssc",
        ).returning(users.c.id)
    ).scalar_one()


def create_topic(slug, level="ssc"):
    topics = db.metadata.tables["topics"]

    return db.session.execute(
        topics.insert().values(
            title=slug,
            slug=slug,
            description="Test lesson",
            display_order=1,
            subject="ict",
            academic_level=level,
        ).returning(topics.c.id)
    ).scalar_one()
def add_attempt(student_id, topic_id, score, completed_at):
    attempts = db.metadata.tables["quiz_attempts"]

    db.session.execute(
        attempts.insert().values(
            user_id=student_id,
            topic_id=topic_id,
            score=score,
            total_questions=5,
            completed_at=completed_at,
        )
    )


def collect(student_id):
    return collect_weekly_report_data(
        student_id=student_id,
        period_start=REPORT_START,
        period_end=REPORT_END,
    )


def test_empty_report_does_not_invent_scores_or_weak_topics(app):
    with app.app_context():
        student_id = create_student()
        create_topic("unattempted-topic")
        db.session.commit()

        report = collect(student_id)

        assert report["quiz_activity"]["completed_attempts"] == 0
        assert report["quiz_activity"]["overall_percentage"] is None
        assert report["weak_topics"] == []
        assert (
            report["learning_assignments"]["written_submissions"] == 0
        )
        assert (
            report["learning_assignments"]["practical_submissions"] == 0
        )


def test_report_counts_window_and_uses_latest_topic_score(app):
    with app.app_context():
        student_id = create_student()
        improved_topic = create_topic("improved-topic")
        weak_topic = create_topic("weak-topic")
        other_level_topic = create_topic("hsc-topic", level="hsc")

        # Old weak result is replaced by the newer 80% result.
        add_attempt(
            student_id,
            improved_topic,
            1,
            REPORT_START - timedelta(days=1),
        )
        add_attempt(
            student_id,
            improved_topic,
            4,
            REPORT_START,
        )

        add_attempt(
            student_id,
            weak_topic,
            2,
            REPORT_END - timedelta(hours=1),
        )

        # End boundary and future attempts must be excluded.
        add_attempt(student_id, weak_topic, 5, REPORT_END)
        add_attempt(
            student_id,
            weak_topic,
            5,
            REPORT_END + timedelta(minutes=1),
        )

        # Another study level must be excluded.
        add_attempt(
            student_id,
            other_level_topic,
            5,
            REPORT_END - timedelta(hours=2),
        )

        db.session.commit()
        report = collect(student_id)

        activity = report["quiz_activity"]

        assert activity["completed_attempts"] == 2
        assert activity["topics_practised"] == 2
        assert activity["correct_answers"] == 6
        assert activity["total_questions"] == 10
        assert activity["overall_percentage"] == 60.0

        assert len(report["weak_topics"]) == 1
        assert report["weak_topics"][0]["topic_id"] == weak_topic
        assert report["weak_topics"][0]["latest_percentage"] == 40.0


def test_report_rejects_missing_student(app):
    with app.app_context():
        with pytest.raises(ValueError, match="valid student"):
            collect(999999)


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (REPORT_END, REPORT_START),
        (REPORT_END, REPORT_END),
        (REPORT_START.replace(tzinfo=None), REPORT_END),
    ],
)
def test_report_rejects_invalid_dates(app, start, end):
    with app.app_context():
        with pytest.raises(ValueError):
            collect_weekly_report_data(
                student_id=999999,
                period_start=start,
                period_end=end,
            )

def insert_test_row(table_name, **values):
    table = db.metadata.tables[table_name]

    return db.session.execute(
        table.insert().values(**values).returning(table.c.id)
    ).scalar_one()


def create_report_class():
    teacher_id = insert_test_row(
        "users",
        name="Report Teacher",
        email="report-teacher@example.com",
        password_hash="test-only",
        role="teacher",
    )

    classroom_id = insert_test_row(
        "classrooms",
        name="Report Class",
        teacher_id=teacher_id,
        join_code="REPORT01",
    )

    return teacher_id, classroom_id


@pytest.mark.parametrize("review_released", [False, True])
def test_assigned_quiz_score_waits_for_review_time(
    app, review_released
):
    with app.app_context():
        student_id = create_student()
        topic_id = create_topic("assigned-topic")
        teacher_id, classroom_id = create_report_class()

        quiz_id = insert_test_row(
            "teacher_quizzes",
            teacher_id=teacher_id,
            topic_id=topic_id,
            title="Assigned quiz",
            response_language="english",
            question_count=5,
            learning_mode="personal_growth",
            status="published",
            questions=[],
        )

        deadline = REPORT_END - timedelta(hours=2)
        review_at = (
            REPORT_END
            if review_released
            else REPORT_END + timedelta(hours=1)
        )

        assignment_id = insert_test_row(
            "quiz_assignments",
            quiz_id=quiz_id,
            classroom_id=classroom_id,
            audience="all",
            available_at=REPORT_START,
            deadline_at=deadline,
            time_limit_minutes=10,
            max_attempts=1,
            review_at=review_at,
        )

        submitted_at = REPORT_END - timedelta(hours=3)

        quiz_attempt_id = insert_test_row(
            "quiz_attempts",
            user_id=student_id,
            topic_id=topic_id,
            score=2,
            total_questions=5,
            completed_at=submitted_at,
        )

        insert_test_row(
            "quiz_assignment_attempts",
            assignment_id=assignment_id,
            student_id=student_id,
            attempt_number=1,
            started_at=submitted_at - timedelta(minutes=5),
            expires_at=submitted_at + timedelta(minutes=5),
            submitted_at=submitted_at,
            answers={},
            total_questions=5,
            score=2,
            quiz_attempt_id=quiz_attempt_id,
        )

        db.session.commit()
        report = collect(student_id)

        assert report["quiz_activity"]["completed_attempts"] == (
            1 if review_released else 0
        )
        assert len(report["weak_topics"]) == (
            1 if review_released else 0
        )


def test_learning_report_counts_submissions_reviews_and_due_tasks(app):
    with app.app_context():
        student_id = create_student()
        teacher_id, classroom_id = create_report_class()

        def create_task(title, task_type):
            assignment_id = insert_test_row(
                "learning_assignments",
                classroom_id=classroom_id,
                title=title,
                instructions="Complete this task.",
                task_type=task_type,
                audience="all",
                total_marks="10.00",
                available_at=REPORT_START,
                deadline_at=REPORT_END - timedelta(hours=1),
                reference_answer="",
            )

            return insert_test_row(
                "learning_assignment_recipients",
                assignment_id=assignment_id,
                student_id=student_id,
                created_at=REPORT_START,
            )

        written_recipient = create_task("Written task", "written")
        practical_recipient = create_task("Practical task", "practical")
        future_recipient = create_task("Late task", "written")

        insert_test_row(
            "learning_assignment_submissions",
            recipient_id=written_recipient,
            answer_text="Student answer",
            code_text="",
            submitted_at=REPORT_END - timedelta(hours=3),
            obtained_marks="8.00",
            feedback="Good work",
            reviewed_by=teacher_id,
            reviewed_at=REPORT_END - timedelta(hours=2),
        )

        insert_test_row(
            "learning_assignment_submissions",
            recipient_id=practical_recipient,
            answer_text="",
            code_text="print('Hello')",
            submitted_at=REPORT_END - timedelta(hours=3),
        )

        # A submission at the end boundary belongs to the next window.
        insert_test_row(
            "learning_assignment_submissions",
            recipient_id=future_recipient,
            answer_text="Late answer",
            code_text="",
            submitted_at=REPORT_END,
        )

        db.session.commit()
        report = collect(student_id)
        tasks = report["learning_assignments"]

        assert tasks["written_submissions"] == 1
        assert tasks["practical_submissions"] == 1
        assert tasks["teacher_reviews_received"] == 1
        assert tasks["reviewed_results"] == [
            {
                "title": "Written task",
                "obtained_marks": "8.00",
                "total_marks": "10.00",
            }
        ]
        assert tasks["tasks_due_this_period"] == 3
        assert tasks["due_tasks_without_submission"] == [
            {
                "title": "Late task",
                "task_type": "written",
            }
        ]