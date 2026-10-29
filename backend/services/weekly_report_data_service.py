from datetime import datetime, timezone

from sqlalchemy import and_, exists, select

from extensions import db
from models.learning_assignment import LearningAssignment
from models.learning_assignment_recipient import LearningAssignmentRecipient
from models.learning_assignment_submission import LearningAssignmentSubmission
from models.quiz_assignment import QuizAssignment
from models.quiz_assignment_attempt import QuizAssignmentAttempt
from models.quiz_attempt import QuizAttempt
from models.topic import Topic
from models.user import User


def utc_datetime(value: datetime) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError("Report dates must include a timezone.")

    return value.astimezone(timezone.utc)


def collect_weekly_report_data(
    *,
    student_id: int,
    period_start: datetime,
    period_end: datetime,
) -> dict:
    period_start = utc_datetime(period_start)
    period_end = utc_datetime(period_end)

    if period_end <= period_start:
        raise ValueError("Report end must be after report start.")

    users = db.metadata.tables["users"]
    topics = db.metadata.tables["topics"]
    attempts = db.metadata.tables["quiz_attempts"]
    quiz_assignments = db.metadata.tables["quiz_assignments"]
    assigned_attempts = db.metadata.tables["quiz_assignment_attempts"]
    assignments = db.metadata.tables["learning_assignments"]
    recipients = db.metadata.tables["learning_assignment_recipients"]
    submissions = db.metadata.tables["learning_assignment_submissions"]
    student = db.session.execute(
        select(
            users.c.id,
            users.c.name,
            users.c.role,
            users.c.academic_level,
        ).where(users.c.id == student_id)
    ).mappings().one_or_none()

    if student is None or student["role"] != "student":
        raise ValueError("A valid student is required.")

    if student["academic_level"] not in {"ssc", "hsc"}:
        raise ValueError("The student must have a study level.")

    # Assigned quiz scores stay hidden until the teacher's review time.
    hidden_assigned_score = exists(
        select(assigned_attempts.c.id)
        .select_from(
            assigned_attempts.join(
                quiz_assignments,
                quiz_assignments.c.id
                == assigned_attempts.c.assignment_id,
            )
        )
        .where(
            assigned_attempts.c.quiz_attempt_id == attempts.c.id,
            quiz_assignments.c.review_at > period_end,
        )
    )

    rows = db.session.execute(
        select(
            attempts.c.id,
            attempts.c.topic_id,
            attempts.c.score,
            attempts.c.total_questions,
            attempts.c.completed_at,
            topics.c.title,
        )
        .select_from(
            attempts.join(
                topics,
                topics.c.id == attempts.c.topic_id,
            )
        )
        .where(
            attempts.c.user_id == student_id,
            attempts.c.completed_at < period_end,
            topics.c.academic_level == student["academic_level"],
            topics.c.subject == "ict",
            ~hidden_assigned_score,
        )
        .order_by(
            attempts.c.completed_at.desc(),
            attempts.c.id.desc(),
        )
    ).mappings().all()

    recent_rows = [
        row
        for row in rows
        if (
            row["completed_at"].replace(tzinfo=timezone.utc)
            if row["completed_at"].tzinfo is None
            else row["completed_at"].astimezone(timezone.utc)
        ) >= period_start
    ]

    latest_by_topic = {}

    for row in rows:
        latest_by_topic.setdefault(row["topic_id"], row)

    weak_topics = []

    for row in latest_by_topic.values():
        if row["score"] * 100 < row["total_questions"] * 80:
            weak_topics.append({
                "topic_id": row["topic_id"],
                "title": row["title"],
                "latest_score": row["score"],
                "total_questions": row["total_questions"],
                "latest_percentage": round(
                    row["score"] / row["total_questions"] * 100,
                    1,
                ),
            })

    weak_topics.sort(
        key=lambda item: (
            item["latest_score"] / item["total_questions"],
            item["topic_id"],
        )
    )

    total_correct = sum(row["score"] for row in recent_rows)
    total_questions = sum(
        row["total_questions"] for row in recent_rows
    )

    # Count submissions once, using their recipient record.
    submitted_rows = db.session.execute(
        select(
            assignments.c.task_type,
            submissions.c.submitted_at,
        )
        .select_from(
            submissions.join(
                recipients,
                recipients.c.id == submissions.c.recipient_id,
            ).join(
                assignments,
                assignments.c.id == recipients.c.assignment_id,
            )
        )
        .where(
            recipients.c.student_id == student_id,
            submissions.c.submitted_at >= period_start,
            submissions.c.submitted_at < period_end,
        )
    ).mappings().all()

    reviewed_rows = db.session.execute(
        select(
            assignments.c.title,
            assignments.c.total_marks,
            submissions.c.obtained_marks,
        )
        .select_from(
            submissions.join(
                recipients,
                recipients.c.id == submissions.c.recipient_id,
            ).join(
                assignments,
                assignments.c.id == recipients.c.assignment_id,
            )
        )
        .where(
            recipients.c.student_id == student_id,
            submissions.c.reviewed_at >= period_start,
            submissions.c.reviewed_at < period_end,
        )
        .order_by(submissions.c.reviewed_at, submissions.c.id)
    ).mappings().all()

    # Tasks available by the report end, whose deadlines fall this week.
    # A submission after the reporting window does not count yet.
    due_rows = db.session.execute(
        select(
            assignments.c.title,
            assignments.c.task_type,
            submissions.c.id.label("submission_id"),
        )
        .select_from(
            recipients.join(
                assignments,
                assignments.c.id == recipients.c.assignment_id,
            ).outerjoin(
                submissions,
                and_(
                    submissions.c.recipient_id == recipients.c.id,
                    submissions.c.submitted_at < period_end,
                ),
            )
        )
        .where(
            recipients.c.student_id == student_id,
            recipients.c.created_at < period_end,
            assignments.c.available_at < period_end,
            assignments.c.deadline_at >= period_start,
            assignments.c.deadline_at < period_end,
        )
        .order_by(assignments.c.deadline_at, assignments.c.id)
    ).mappings().all()

    return {
        "student_name": student["name"],
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "quiz_activity": {
            "completed_attempts": len(recent_rows),
            "topics_practised": len({
                row["topic_id"] for row in recent_rows
            }),
            "correct_answers": total_correct,
            "total_questions": total_questions,
            "overall_percentage": (
                round(total_correct / total_questions * 100, 1)
                if total_questions
                else None
            ),
            "basis": (
                "Completed ICT attempts during the reporting period; "
                "assigned scores awaiting teacher review are excluded."
            ),
        },
        "weak_topics": weak_topics,
        "weak_topic_basis": (
            "Latest available completed ICT attempt per topic before "
            "report end; score below 80%. This is current status, "
            "not necessarily activity from this week."
        ),
        "learning_assignments": {
            "written_submissions": sum(
                row["task_type"] == "written"
                for row in submitted_rows
            ),
            "practical_submissions": sum(
                row["task_type"] == "practical"
                for row in submitted_rows
            ),
            "teacher_reviews_received": len(reviewed_rows),
            "reviewed_results": [
                {
                    "title": row["title"],
                    "obtained_marks": str(row["obtained_marks"]),
                    "total_marks": str(row["total_marks"]),
                }
                for row in reviewed_rows
            ],
            "tasks_due_this_period": len(due_rows),
            "due_tasks_without_submission": [
                {
                    "title": row["title"],
                    "task_type": row["task_type"],
                }
                for row in due_rows
                if row["submission_id"] is None
            ],
        },
    }