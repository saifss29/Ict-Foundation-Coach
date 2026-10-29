from datetime import datetime, timedelta, timezone
from typing import Any, cast


from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from marshmallow import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from models.class_membership import ClassMembership
from models.classroom import Classroom
from models.notification import Notification
from models.quiz_assignment import QuizAssignment
from models.quiz_assignment_recipient import QuizAssignmentRecipient
from models.teacher_quiz import TeacherQuiz
from models.user import User
from schemas.quiz_assignment_schema import CreateQuizAssignmentSchema
from models.quiz_assignment_attempt import QuizAssignmentAttempt
from schemas.teacher_quiz_schema import UpdateTeacherQuizSchema
from models.quiz_attempt import QuizAttempt
from schemas.quiz_assignment_attempt_schema import (
    QuizAssignmentAnswersSchema,
)


quiz_assignments_bp = Blueprint(
    "quiz_assignments",
    __name__,
    url_prefix="/api/quiz-assignments",
)

create_assignment_schema = CreateQuizAssignmentSchema()
assignment_answers_schema = QuizAssignmentAnswersSchema()

def serialize_assignment(
    assignment: QuizAssignment,
    *,
    recipient_count: int,
):
    return {
        "id": assignment.id,
        "quiz_id": assignment.quiz_id,
        "classroom_id": assignment.classroom_id,
        "audience": assignment.audience,
        "available_at": assignment.available_at.isoformat(),
        "deadline_at": assignment.deadline_at.isoformat(),
        "time_limit_minutes": assignment.time_limit_minutes,
        "max_attempts": assignment.max_attempts,
        "review_at": assignment.review_at.isoformat(),
        "recipient_count": recipient_count,
        "created_at": assignment.created_at.isoformat(),
    }


@quiz_assignments_bp.post("")
@jwt_required()
def create_quiz_assignment():
    teacher = db.session.get(User, int(get_jwt_identity()))

    if teacher is None:
        return jsonify({
            "error": "User account no longer exists"
        }), 404

    if teacher.role != "teacher":
        return jsonify({
            "error": "Only teachers can assign quizzes"
        }), 403

    request_data = request.get_json(silent=True)

    if not isinstance(request_data, dict):
        return jsonify({
            "error": "Request body must be a JSON object"
        }), 400

    try:
        data = cast(
            dict[str, Any],
            create_assignment_schema.load(request_data),
        )
    except ValidationError as error:
        return jsonify({
            "error": "Validation failed",
            "messages": error.messages,
        }), 400

    try:
        classroom = db.session.scalar(
            db.select(Classroom).where(
                Classroom.id == data["classroom_id"],
                Classroom.teacher_id == teacher.id,
            )
        )

        if classroom is None:
            db.session.rollback()
            return jsonify({
                "error": "Class not found"
            }), 404

        quiz = db.session.scalar(
            db.select(TeacherQuiz).where(
                TeacherQuiz.id == data["quiz_id"],
                TeacherQuiz.teacher_id == teacher.id,
            )
        )

        if quiz is None:
            db.session.rollback()
            return jsonify({
                "error": "Teacher quiz not found"
            }), 404

        if quiz.status != "published":
            db.session.rollback()
            return jsonify({
                "error": "Publish the quiz before assigning it."
            }), 409

        if data["deadline_at"] <= datetime.now(timezone.utc):
            db.session.rollback()
            return jsonify({
                "error": "Deadline must be in the future."
            }), 400

        membership_query = (
            db.select(ClassMembership)
            .join(
                User,
                User.id == ClassMembership.student_id,
            )
            .where(
                ClassMembership.classroom_id == classroom.id,
                User.role == "student",
            )
            .order_by(ClassMembership.student_id)
        )

        if data["audience"] == "selected":
            memberships_table = db.metadata.tables["class_memberships"]

            membership_query = membership_query.where(
                memberships_table.c["student_id"].in_(
                    data["student_ids"]
                )
            )

        # Lock recipient memberships while the assignment is saved.
        # PostgreSQL enforces these row locks.
        memberships = db.session.scalars(
            membership_query.with_for_update(
                of=ClassMembership,
            )
        ).all()

        recipient_ids = [
            membership.student_id
            for membership in memberships
        ]

        if data["audience"] == "selected":
            if set(recipient_ids) != set(data["student_ids"]):
                db.session.rollback()
                return jsonify({
                    "error": (
                        "Every selected student must be a current "
                        "member of this class."
                    )
                }), 400

        if not recipient_ids:
            db.session.rollback()
            return jsonify({
                "error": "No enrolled students are available for this assignment."
            }), 400

        assignment = QuizAssignment(
            quiz_id=quiz.id,
            classroom_id=classroom.id,
            audience=data["audience"],
            available_at=data["available_at"],
            deadline_at=data["deadline_at"],
            time_limit_minutes=data["time_limit_minutes"],
            max_attempts=data["max_attempts"],
            review_at=data["review_at"],
        )

        db.session.add(assignment)
        db.session.flush()

        for student_id in recipient_ids:
            db.session.add(
                QuizAssignmentRecipient(
                    assignment_id=assignment.id,
                    student_id=student_id,
                )
            )

            db.session.add(
                Notification(
                    user_id=student_id,
                    notification_type="quiz_assignment",
                    title="New assigned quiz",
                    message=(
                        f'{teacher.name} assigned "{quiz.title}" '
                        f'to you in "{classroom.name}".'
                    ),
                )
            )

        # Save settings, recipients and notifications together.
        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Could not assign quiz. Try again later."
        }), 500

    return jsonify({
        "message": "Quiz assigned successfully",
        "assignment": serialize_assignment(
            assignment,
            recipient_count=len(recipient_ids),
        ),
    }), 201


@quiz_assignments_bp.get("")
@jwt_required()
def list_quiz_assignments():
    user = db.session.get(User, int(get_jwt_identity()))

    if user is None:
        return jsonify({
            "error": "User account no longer exists"
        }), 404

    if user.role not in {"teacher", "student"}:
        return jsonify({
            "error": "Only teachers and students can view assignments"
        }), 403

    raw_page = request.args.get("page", "1")
    list_view = request.args.get("view", "active")

    if list_view not in {"active", "history"}:
        return jsonify({
            "error": "View must be active or history"
        }), 400

    if user.role == "teacher" and list_view == "history":
        return jsonify({
            "error": "Assignment history is available only to students"
        }), 403

    try:
        page = int(raw_page)
    except ValueError:
        return jsonify({
            "error": "Page must be a positive integer"
        }), 400

    if page < 1 or page > 10000:
        return jsonify({
            "error": "Page must be between 1 and 10000"
        }), 400



    page_size = 20

    assignments_table = db.metadata.tables["quiz_assignments"]
    recipients_table = db.metadata.tables["quiz_assignment_recipients"]
    quizzes_table = db.metadata.tables["teacher_quizzes"]
    classrooms_table = db.metadata.tables["classrooms"]
    users_table = db.metadata.tables["users"]
    attempts_table = db.metadata.tables["quiz_assignment_attempts"]

    has_submitted_attempt = (
        db.select(attempts_table.c["id"])
        .where(
            attempts_table.c["assignment_id"]
            == assignments_table.c["id"],
            attempts_table.c["student_id"] == user.id,
            attempts_table.c["submitted_at"].is_not(None),
        )
        .correlate(assignments_table)
        .exists()
        .label("has_submitted_attempt")
    )

    recipient_count = (
        db.select(db.func.count(recipients_table.c["id"]))
        .where(
            recipients_table.c["assignment_id"]
            == assignments_table.c["id"]
        )
        .correlate(assignments_table)
        .scalar_subquery()
        .label("recipient_count")
    )

    query = (
        db.select(
            QuizAssignment,
            quizzes_table.c["title"].label("quiz_title"),
            quizzes_table.c["question_count"].label("question_count"),
            quizzes_table.c["response_language"].label(
                "response_language"
            ),
            classrooms_table.c["name"].label("classroom_name"),
            users_table.c["name"].label("teacher_name"),
            recipient_count,
            has_submitted_attempt,
        )
        .join(
            TeacherQuiz,
            TeacherQuiz.id == QuizAssignment.quiz_id,
        )
        .join(
            Classroom,
            Classroom.id == QuizAssignment.classroom_id,
        )
        .join(
            User,
            User.id == TeacherQuiz.teacher_id,
        )
    )

    if user.role == "teacher":
        query = query.where(
            TeacherQuiz.teacher_id == user.id,
            Classroom.teacher_id == user.id,
        )
    else:
        # Only this student's saved recipient record controls visibility.
        removed_at = recipients_table.c["removed_at"]

        visibility_filter = (
            removed_at.is_not(None)
            if list_view == "history"
            else removed_at.is_(None)
        )

        is_recipient = (
            db.select(recipients_table.c["id"])
            .where(
                recipients_table.c["assignment_id"]
                == assignments_table.c["id"],
                recipients_table.c["student_id"] == user.id,
                visibility_filter,
            )
            .correlate(assignments_table)
            .exists()
        )

        query = query.where(is_recipient)

    query = (
        query
        .order_by(
            assignments_table.c["created_at"].desc(),
            assignments_table.c["id"].desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size + 1)
    )

    try:
        rows = db.session.execute(query).mappings().all()

        assignments = []

        for row in rows[:page_size]:
            item = serialize_assignment(
                row["QuizAssignment"],
                recipient_count=row["recipient_count"],
            )

            item.update({
                "quiz_title": row["quiz_title"],
                "question_count": row["question_count"],
                "response_language": row["response_language"],
                "classroom_name": row["classroom_name"],
                "teacher_name": row["teacher_name"],
            })
            if user.role == "student":
                item.pop("recipient_count")
                item["can_remove"] = (
                    list_view == "active"
                    and bool(row["has_submitted_attempt"])
                )
            assignments.append(item)

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Could not load assignments. Try again later."
        }), 500

    return jsonify({
        "assignments": assignments,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "has_more": len(rows) > page_size,
        },
    }), 200


def as_utc(value: datetime) -> datetime:
    # SQLite test timestamps may lose timezone information.
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def serialize_active_assignment_attempt(
    attempt: QuizAssignmentAttempt,
    assignment: QuizAssignment,
    quiz: TeacherQuiz,
    questions: list[dict[str, Any]],
    now: datetime,
):
    public_fields = (
        "id",
        "question_text",
        "option_a",
        "option_b",
        "option_c",
        "option_d",
    )

    return {
        "id": attempt.id,
        "assignment_id": assignment.id,
        "quiz_title": quiz.title,
        "response_language": quiz.response_language,
        "attempt_number": attempt.attempt_number,
        "max_attempts": assignment.max_attempts,
        "total_questions": attempt.total_questions,
        "started_at": as_utc(attempt.started_at).isoformat(),
        "expires_at": as_utc(attempt.expires_at).isoformat(),
        "server_time": now.isoformat(),
        "answers": attempt.answers,
        "questions": [
            {
                field: question[field]
                for field in public_fields
            }
            for question in questions
        ],
    }


@quiz_assignments_bp.post("/<string:assignment_id>/start")
@jwt_required()
def start_quiz_assignment(assignment_id):
    student = db.session.get(User, int(get_jwt_identity()))

    if student is None:
        return jsonify({
            "error": "User account no longer exists"
        }), 404

    if student.role != "student":
        return jsonify({
            "error": "Only students can start assigned quizzes"
        }), 403

    request_data = request.get_json(silent=True)

    if not isinstance(request_data, dict) or request_data:
        return jsonify({
            "error": "Request body must be an empty JSON object"
        }), 400

    try:
        # Serialize starts for this student and assignment.
        # The submit route must acquire this same lock.
        recipient = db.session.scalar(
            db.select(QuizAssignmentRecipient)
            .where(
                QuizAssignmentRecipient.assignment_id == assignment_id,
                QuizAssignmentRecipient.student_id == student.id,
            )
            .with_for_update(of=QuizAssignmentRecipient)
        )

        if recipient is None:
            db.session.rollback()
            return jsonify({
                "error": "Assignment not found"
            }), 404

        assignment = db.session.get(QuizAssignment, assignment_id)

        if assignment is None:
            db.session.rollback()
            return jsonify({
                "error": "Assignment not found"
            }), 404

        now = datetime.now(timezone.utc)
        available_at = as_utc(assignment.available_at)
        deadline_at = as_utc(assignment.deadline_at)

        if now < available_at:
            db.session.rollback()
            return jsonify({
                "error": "This quiz is not available yet."
            }), 409

        if now >= deadline_at:
            db.session.rollback()
            return jsonify({
                "error": "The assignment deadline has passed."
            }), 409

        quiz = db.session.get(TeacherQuiz, assignment.quiz_id)

        if quiz is None or quiz.status != "published":
            db.session.rollback()
            return jsonify({
                "error": "The assigned quiz is unavailable."
            }), 409

        # Revalidate stored questions before starting an attempt.
        try:
            validated = cast(
                dict[str, Any],
                UpdateTeacherQuizSchema(
                    expected_question_count=quiz.question_count,
                ).load({
                    "title": quiz.title,
                    "questions": quiz.questions,
                }),
            )
        except (ValidationError, ValueError, TypeError):
            db.session.rollback()
            return jsonify({
                "error": "The saved quiz is invalid. Contact your teacher."
            }), 409

        questions = validated["questions"]
        attempts_table = db.metadata.tables["quiz_assignment_attempts"]

        latest_attempt = db.session.scalar(
            db.select(QuizAssignmentAttempt)
            .where(
                QuizAssignmentAttempt.assignment_id == assignment.id,
                QuizAssignmentAttempt.student_id == student.id,
            )
            .order_by(
                attempts_table.c["attempt_number"].desc()
            )
            .limit(1)
        )

        if (
            latest_attempt is not None
            and latest_attempt.submitted_at is None
            and now < as_utc(latest_attempt.expires_at)
        ):
            # Refreshing/resuming does not restart the timer.
            result = serialize_active_assignment_attempt(
                latest_attempt,
                assignment,
                quiz,
                questions,
                now,
            )
            db.session.commit()

            return jsonify({
                "message": "Existing attempt resumed",
                "attempt": result,
            }), 200

        next_number = (
            latest_attempt.attempt_number + 1
            if latest_attempt is not None
            else 1
        )

        if next_number > assignment.max_attempts:
            db.session.rollback()
            return jsonify({
                "error": "You have used all allowed attempts."
            }), 409

        # Expired attempts also consume an attempt.
        expires_at = min(
            now + timedelta(minutes=assignment.time_limit_minutes),
            deadline_at,
        )

        attempt = QuizAssignmentAttempt(
            assignment_id=assignment.id,
            student_id=student.id,
            attempt_number=next_number,
            started_at=now,
            expires_at=expires_at,
            total_questions=len(questions),
        )

        db.session.add(attempt)
        db.session.flush()

        result = serialize_active_assignment_attempt(
            attempt,
            assignment,
            quiz,
            questions,
            now,
        )

        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Could not start quiz. Try again later."
        }), 500

    return jsonify({
        "message": "Quiz attempt started",
        "attempt": result,
    }), 201


def assignment_attempt_result(attempt, assignment):
    return {
        "id": attempt.id,
        "assignment_id": assignment.id,
        "attempt_number": attempt.attempt_number,
        "score": attempt.score,
        "total_questions": attempt.total_questions,
        "submitted_at": as_utc(attempt.submitted_at).isoformat(),
        "review_at": as_utc(assignment.review_at).isoformat(),
    }


def handle_assignment_answers(assignment_id, attempt_id, *, submit):
    student = db.session.get(User, int(get_jwt_identity()))

    if student is None:
        return jsonify({
            "error": "User account no longer exists"
        }), 404

    if student.role != "student":
        return jsonify({
            "error": "Only students can answer assigned quizzes"
        }), 403

    request_data = request.get_json(silent=True)

    if not isinstance(request_data, dict):
        return jsonify({
            "error": "Request body must be a JSON object"
        }), 400

    try:
        data = cast(
            dict[str, Any],
            assignment_answers_schema.load(request_data),
        )
    except ValidationError as error:
        return jsonify({
            "error": "Validation failed",
            "messages": error.messages,
        }), 400

    try:
        # Use the same lock order as the Start API.
        recipient = db.session.scalar(
            db.select(QuizAssignmentRecipient)
            .where(
                QuizAssignmentRecipient.assignment_id == assignment_id,
                QuizAssignmentRecipient.student_id == student.id,
            )
            .with_for_update(of=QuizAssignmentRecipient)
        )

        if recipient is None:
            db.session.rollback()
            return jsonify({
                "error": "Assignment not found"
            }), 404

        assignment = db.session.get(QuizAssignment, assignment_id)

        attempt = db.session.scalar(
            db.select(QuizAssignmentAttempt)
            .where(
                QuizAssignmentAttempt.id == attempt_id,
                QuizAssignmentAttempt.assignment_id == assignment_id,
                QuizAssignmentAttempt.student_id == student.id,
            )
            .with_for_update(of=QuizAssignmentAttempt)
        )

        if assignment is None or attempt is None:
            db.session.rollback()
            return jsonify({
                "error": "Quiz attempt not found"
            }), 404

        if attempt.submitted_at is not None:
            # Retrying a completed submit returns the saved result.
            if submit:
                result = assignment_attempt_result(attempt, assignment)
                db.session.commit()
                return jsonify({
                    "message": "Quiz already submitted",
                    "result": result,
                }), 200

            db.session.rollback()
            return jsonify({
                "error": "Submitted answers cannot be changed."
            }), 409

        quiz = db.session.get(TeacherQuiz, assignment.quiz_id)

        if quiz is None or quiz.status != "published":
            db.session.rollback()
            return jsonify({
                "error": "The assigned quiz is unavailable."
            }), 409

        try:
            validated = cast(
                dict[str, Any],
                UpdateTeacherQuizSchema(
                    expected_question_count=quiz.question_count,
                ).load({
                    "title": quiz.title,
                    "questions": quiz.questions,
                }),
            )
        except (ValidationError, ValueError, TypeError):
            db.session.rollback()
            return jsonify({
                "error": "The saved quiz is invalid. Contact your teacher."
            }), 409

        questions = validated["questions"]

        if len(questions) != attempt.total_questions:
            db.session.rollback()
            return jsonify({
                "error": "The quiz no longer matches this attempt."
            }), 409

        question_ids = {question["id"] for question in questions}
        incoming_answers = data["answers"]

        if not set(incoming_answers).issubset(question_ids):
            db.session.rollback()
            return jsonify({
                "error": "Answers contain an unknown question ID."
            }), 400

        now = datetime.now(timezone.utc)

        if now < as_utc(attempt.started_at):
            db.session.rollback()
            return jsonify({
                "error": "The attempt has not started yet."
            }), 409

        expired = (
            now >= as_utc(attempt.expires_at)
            or now >= as_utc(assignment.deadline_at)
        )

        if not expired:
            # Every save sends the complete current answer map.
            attempt.answers = dict(incoming_answers)

        if not submit and not expired:
            saved_response = {
                "id": attempt.id,
                "assignment_id": assignment.id,
                "answers": attempt.answers,
                "expires_at": as_utc(attempt.expires_at).isoformat(),
                "server_time": now.isoformat(),
            }

            db.session.commit()
            return jsonify({
                "message": "Answers saved",
                "attempt": saved_response,
            }), 200

        # At expiry, grade only answers already stored on the server.
        score = sum(
            attempt.answers.get(question["id"])
            == question["correct_option"]
            for question in questions
        )

        progress = QuizAttempt(
            user_id=student.id,
            topic_id=quiz.topic_id,
            score=score,
            total_questions=attempt.total_questions,
        )

        db.session.add(progress)
        db.session.flush()

        attempt.score = score
        attempt.submitted_at = now
        attempt.quiz_attempt_id = progress.id

        result = assignment_attempt_result(attempt, assignment)

        # Save the submitted attempt and progress together.
        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Could not save quiz answers. Try again later."
        }), 500

    return jsonify({
        "message": (
            "Time expired. Previously saved answers were submitted."
            if expired
            else "Quiz submitted successfully"
        ),
        "result": result,
    }), 200


@quiz_assignments_bp.patch(
    "/<string:assignment_id>/attempts/<string:attempt_id>/answers"
)
@jwt_required()
def save_quiz_assignment_answers(assignment_id, attempt_id):
    return handle_assignment_answers(
        assignment_id,
        attempt_id,
        submit=False,
    )


@quiz_assignments_bp.post(
    "/<string:assignment_id>/attempts/<string:attempt_id>/submit"
)
@jwt_required()
def submit_quiz_assignment_attempt(assignment_id, attempt_id):
    return handle_assignment_answers(
        assignment_id,
        attempt_id,
        submit=True,
    )

@quiz_assignments_bp.get(
    "/<string:assignment_id>/attempts/<string:attempt_id>/review"
)
@jwt_required()
def review_quiz_assignment_attempt(assignment_id, attempt_id):
    student = db.session.get(User, int(get_jwt_identity()))

    if student is None:
        return jsonify({
            "error": "User account no longer exists"
        }), 404

    if student.role != "student":
        return jsonify({
            "error": "Only students can review their assigned quiz attempts"
        }), 403

    try:
        recipient = db.session.scalar(
            db.select(QuizAssignmentRecipient.id).where(
                QuizAssignmentRecipient.assignment_id == assignment_id,
                QuizAssignmentRecipient.student_id == student.id,
            )
        )

        if recipient is None:
            return jsonify({
                "error": "Assignment not found"
            }), 404

        assignment = db.session.get(QuizAssignment, assignment_id)

        attempt = db.session.scalar(
            db.select(QuizAssignmentAttempt).where(
                QuizAssignmentAttempt.id == attempt_id,
                QuizAssignmentAttempt.assignment_id == assignment_id,
                QuizAssignmentAttempt.student_id == student.id,
            )
        )

        if assignment is None or attempt is None:
            return jsonify({
                "error": "Quiz attempt not found"
            }), 404

        if attempt.submitted_at is None:
            return jsonify({
                "error": "Submit this attempt before reviewing it."
            }), 409

        now = datetime.now(timezone.utc)

        if now < as_utc(assignment.review_at):
            return jsonify({
                "error": "Quiz review is not available yet.",
                "review_at": as_utc(assignment.review_at).isoformat(),
            }), 409

        quiz = db.session.get(TeacherQuiz, assignment.quiz_id)

        if quiz is None or quiz.status != "published":
            return jsonify({
                "error": "The assigned quiz is unavailable."
            }), 409

        try:
            validated = cast(
                dict[str, Any],
                UpdateTeacherQuizSchema(
                    expected_question_count=quiz.question_count,
                ).load({
                    "title": quiz.title,
                    "questions": quiz.questions,
                }),
            )
        except (ValidationError, ValueError, TypeError):
            return jsonify({
                "error": "The saved quiz is invalid. Contact your teacher."
            }), 409

        questions = validated["questions"]

        if len(questions) != attempt.total_questions:
            return jsonify({
                "error": "The quiz no longer matches this attempt."
            }), 409

        review_questions = []

        for question in questions:
            selected_option = attempt.answers.get(question["id"])

            review_questions.append({
                "id": question["id"],
                "question_text": question["question_text"],
                "option_a": question["option_a"],
                "option_b": question["option_b"],
                "option_c": question["option_c"],
                "option_d": question["option_d"],
                "selected_option": selected_option,
                "correct_option": question["correct_option"],
                "is_correct": (
                    selected_option == question["correct_option"]
                ),
                "explanation": question["explanation"],
            })

        review = assignment_attempt_result(attempt, assignment)
        review.update({
            "quiz_title": quiz.title,
            "response_language": quiz.response_language,
            "questions": review_questions,
        })

        return jsonify({
            "review": review,
        }), 200

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Could not load quiz review. Try again later."
        }), 500

@quiz_assignments_bp.get("/<string:assignment_id>/attempts")
@jwt_required()
def list_my_assignment_attempts(assignment_id):
    student = db.session.get(User, int(get_jwt_identity()))

    if student is None:
        return jsonify({
            "error": "User account no longer exists"
        }), 404

    if student.role != "student":
        return jsonify({
            "error": "Only students can view their assignment attempts"
        }), 403

    try:
        recipient = db.session.scalar(
            db.select(QuizAssignmentRecipient.id).where(
                QuizAssignmentRecipient.assignment_id == assignment_id,
                QuizAssignmentRecipient.student_id == student.id,
            )
        )

        if recipient is None:
            return jsonify({
                "error": "Assignment not found"
            }), 404

        assignment = db.session.get(QuizAssignment, assignment_id)

        if assignment is None:
            return jsonify({
                "error": "Assignment not found"
            }), 404

        attempts_table = db.metadata.tables["quiz_assignment_attempts"]

        attempts = db.session.scalars(
            db.select(QuizAssignmentAttempt)
            .where(
                QuizAssignmentAttempt.assignment_id == assignment_id,
                QuizAssignmentAttempt.student_id == student.id,
            )
            .order_by(
                attempts_table.c["attempt_number"].desc()
            )
        ).all()

        now = datetime.now(timezone.utc)
        items = []

        for attempt in attempts:
            submitted = attempt.submitted_at is not None
            expired = (
                now >= as_utc(attempt.expires_at)
                or now >= as_utc(assignment.deadline_at)
            )

            status = (
                "submitted"
                if submitted
                else "expired"
                if expired
                else "in_progress"
            )

            items.append({
                "id": attempt.id,
                "assignment_id": assignment.id,
                "attempt_number": attempt.attempt_number,
                "status": status,
                "score": attempt.score,
                "total_questions": attempt.total_questions,
                "started_at": as_utc(attempt.started_at).isoformat(),
                "expires_at": as_utc(attempt.expires_at).isoformat(),
                "submitted_at": (
                    as_utc(attempt.submitted_at).isoformat()
                    if submitted
                    else None
                ),
                "review_at": as_utc(assignment.review_at).isoformat(),
                "can_review": (
                    submitted
                    and now >= as_utc(assignment.review_at)
                ),
            })

        return jsonify({
            "assignment_id": assignment.id,
            "max_attempts": assignment.max_attempts,
            "server_time": now.isoformat(),
            "attempts": items,
        }), 200

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Could not load quiz attempts. Try again later."
        }), 500

@quiz_assignments_bp.get("/<string:assignment_id>/results")
@jwt_required()
def get_teacher_assignment_results(assignment_id):
    teacher = db.session.get(User, int(get_jwt_identity()))

    if teacher is None:
        return jsonify({
            "error": "User account no longer exists"
        }), 404

    if teacher.role != "teacher":
        return jsonify({
            "error": "Only teachers can view assignment results"
        }), 403

    raw_page = request.args.get("page", "1")

    try:
        page = int(raw_page)
    except ValueError:
        return jsonify({
            "error": "Page must be a positive integer"
        }), 400

    if page < 1 or page > 10000:
        return jsonify({
            "error": "Page must be between 1 and 10000"
        }), 400

    page_size = 20

    try:
        # Check ownership of both the quiz and its classroom.
        assignment = db.session.scalar(
            db.select(QuizAssignment)
            .join(
                TeacherQuiz,
                TeacherQuiz.id == QuizAssignment.quiz_id,
            )
            .join(
                Classroom,
                Classroom.id == QuizAssignment.classroom_id,
            )
            .where(
                QuizAssignment.id == assignment_id,
                TeacherQuiz.teacher_id == teacher.id,
                Classroom.teacher_id == teacher.id,
            )
        )

        if assignment is None:
            return jsonify({
                "error": "Assignment not found"
            }), 404

        quiz = db.session.get(TeacherQuiz, assignment.quiz_id)
        classroom = db.session.get(Classroom, assignment.classroom_id)

        if quiz is None or classroom is None:
            return jsonify({
                "error": "Assignment not found"
            }), 404

        recipients_table = db.metadata.tables[
            "quiz_assignment_recipients"
        ]
        users_table = db.metadata.tables["users"]
        attempts_table = db.metadata.tables[
            "quiz_assignment_attempts"
        ]

        recipient_count = db.session.scalar(
            db.select(
                db.func.count(recipients_table.c["id"])
            ).where(
                recipients_table.c["assignment_id"] == assignment.id
            )
        ) or 0

        # Use the saved recipients, including students who left the class.
        rows = db.session.execute(
            db.select(
                recipients_table.c["student_id"],
                users_table.c["name"].label("student_name"),
            )
            .select_from(recipients_table)
            .join(
                users_table,
                users_table.c["id"]
                == recipients_table.c["student_id"],
            )
            .where(
                recipients_table.c["assignment_id"] == assignment.id
            )
            .order_by(recipients_table.c["student_id"])
            .offset((page - 1) * page_size)
            .limit(page_size + 1)
        ).mappings().all()

        visible_rows = rows[:page_size]
        student_ids = [
            row["student_id"] for row in visible_rows
        ]

        # Fetch attempts for this page together, avoiding one query per student.
        attempts = []

        if student_ids:
            attempts = db.session.scalars(
                db.select(QuizAssignmentAttempt)
                .where(
                    QuizAssignmentAttempt.assignment_id == assignment.id,
                    attempts_table.c["student_id"].in_(student_ids),
                )
                .order_by(
                    attempts_table.c["student_id"],
                    attempts_table.c["attempt_number"].desc(),
                )
            ).all()

        attempts_by_student = {
            student_id: [] for student_id in student_ids
        }

        now = datetime.now(timezone.utc)
        deadline_at = as_utc(assignment.deadline_at)

        for attempt in attempts:
            submitted = attempt.submitted_at is not None

            if submitted:
                status = "submitted"
            elif (
                now >= as_utc(attempt.expires_at)
                or now >= deadline_at
            ):
                status = "expired"
            else:
                status = "in_progress"

            attempts_by_student[attempt.student_id].append({
                "id": attempt.id,
                "attempt_number": attempt.attempt_number,
                "status": status,
                "score": attempt.score,
                "total_questions": attempt.total_questions,
                "started_at": as_utc(attempt.started_at).isoformat(),
                "expires_at": as_utc(attempt.expires_at).isoformat(),
                "submitted_at": (
                    as_utc(attempt.submitted_at).isoformat()
                    if submitted
                    else None
                ),
            })

        students = []

        for row in visible_rows:
            student_attempts = attempts_by_student[row["student_id"]]

            submitted_attempts = [
                attempt
                for attempt in student_attempts
                if attempt["status"] == "submitted"
            ]

            best_attempt = max(
                submitted_attempts,
                key=lambda attempt: (
                    attempt["score"] / attempt["total_questions"],
                    attempt["attempt_number"],
                ),
                default=None,
            )

            students.append({
                "student_id": row["student_id"],
                "student_name": row["student_name"],
                "latest_status": (
                    student_attempts[0]["status"]
                    if student_attempts
                    else "not_started"
                ),
                "attempts_used": len(student_attempts),
                "submitted_attempts": len(submitted_attempts),
                "best_score": (
                    best_attempt["score"]
                    if best_attempt is not None
                    else None
                ),
                "best_total_questions": (
                    best_attempt["total_questions"]
                    if best_attempt is not None
                    else None
                ),
                "attempts": student_attempts,
            })

        assignment_data = serialize_assignment(
            assignment,
            recipient_count=recipient_count,
        )
        assignment_data.update({
            "quiz_title": quiz.title,
            "classroom_name": classroom.name,
            "question_count": quiz.question_count,
            "response_language": quiz.response_language,
        })

        return jsonify({
            "assignment": assignment_data,
            "server_time": now.isoformat(),
            "students": students,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "has_more": len(rows) > page_size,
            },
        }), 200

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Could not load assignment results. Try again later."
        }), 500

@quiz_assignments_bp.get(
    "/<string:assignment_id>/attempts/<string:attempt_id>/teacher-review"
)
@jwt_required()
def review_assignment_attempt_for_teacher(assignment_id, attempt_id):
    try:
        teacher = db.session.get(User, int(get_jwt_identity()))

        if teacher is None:
            return jsonify({
                "error": "User account no longer exists",
            }), 404

        if teacher.role != "teacher":
            return jsonify({
                "error": "Only teachers can review student submissions",
            }), 403

        assignment = db.session.scalar(
            db.select(QuizAssignment)
            .join(
                TeacherQuiz,
                TeacherQuiz.id == QuizAssignment.quiz_id,
            )
            .join(
                Classroom,
                Classroom.id == QuizAssignment.classroom_id,
            )
            .where(
                QuizAssignment.id == assignment_id,
                TeacherQuiz.teacher_id == teacher.id,
                Classroom.teacher_id == teacher.id,
            )
        )

        if assignment is None:
            return jsonify({
                "error": "Assignment not found",
            }), 404

        # Bind the attempt to this assignment and its saved recipient.
        # Current class membership is not required for historical results.
        attempt = db.session.scalar(
            db.select(QuizAssignmentAttempt)
            .join(
                QuizAssignmentRecipient,
                db.and_(
                    QuizAssignmentRecipient.assignment_id
                    == QuizAssignmentAttempt.assignment_id,
                    QuizAssignmentRecipient.student_id
                    == QuizAssignmentAttempt.student_id,
                ),
            )
            .where(
                QuizAssignmentAttempt.id == attempt_id,
                QuizAssignmentAttempt.assignment_id == assignment.id,
            )
        )

        if attempt is None:
            return jsonify({
                "error": "Quiz attempt not found",
            }), 404

        if attempt.submitted_at is None:
            return jsonify({
                "error": "This attempt has not been submitted.",
            }), 409

        quiz = db.session.get(TeacherQuiz, assignment.quiz_id)
        classroom = db.session.get(Classroom, assignment.classroom_id)
        student = db.session.get(User, attempt.student_id)

        if classroom is None or student is None:
            return jsonify({
                "error": "Submission details not found",
            }), 404

        if quiz is None or quiz.status != "published":
            return jsonify({
                "error": "The assigned quiz is unavailable.",
            }), 409

        try:
            validated = cast(
                dict[str, Any],
                UpdateTeacherQuizSchema(
                    expected_question_count=quiz.question_count,
                ).load({
                    "title": quiz.title,
                    "questions": quiz.questions,
                }),
            )
        except (ValidationError, ValueError, TypeError):
            return jsonify({
                "error": "The saved quiz is invalid.",
            }), 409

        questions = validated["questions"]

        if len(questions) != attempt.total_questions:
            return jsonify({
                "error": "The quiz no longer matches this attempt.",
            }), 409

        review_questions = []

        for question in questions:
            selected_option = attempt.answers.get(question["id"])

            review_questions.append({
                "id": question["id"],
                "question_text": question["question_text"],
                "option_a": question["option_a"],
                "option_b": question["option_b"],
                "option_c": question["option_c"],
                "option_d": question["option_d"],
                "selected_option": selected_option,
                "correct_option": question["correct_option"],
                "is_correct": (
                    selected_option == question["correct_option"]
                ),
                "explanation": question["explanation"],
            })

        review = assignment_attempt_result(attempt, assignment)
        review.update({
            "quiz_attempt_id": attempt.quiz_attempt_id,
            "student_id": student.id,
            "student_name": student.name,
            "classroom_id": classroom.id,
            "classroom_name": classroom.name,
            "quiz_title": quiz.title,
            "response_language": quiz.response_language,
            "started_at": as_utc(attempt.started_at).isoformat(),
            "questions": review_questions,
        })

        return jsonify({
            "review": review,
        }), 200

    except SQLAlchemyError:
        db.session.rollback()

        return jsonify({
            "error": "Could not load student submission. Try again later.",
        }), 500

@quiz_assignments_bp.get(
    "/<string:assignment_id>/mistake-report"
)
@jwt_required()
def get_teacher_assignment_mistake_report(assignment_id):
    raw_page = request.args.get("page", "1")
    status_filter = request.args.get("status", "all")

    try:
        page = int(raw_page)
    except ValueError:
        return jsonify({
            "error": "Page must be a positive integer"
        }), 400

    if not 1 <= page <= 10000:
        return jsonify({
            "error": "Page must be between 1 and 10000"
        }), 400

    allowed_filters = {
        "all",
        "not_started",
        "not_submitted",
        "submitted",
    }

    if status_filter not in allowed_filters:
        return jsonify({
            "error": (
                "Status must be all, not_started, "
                "not_submitted or submitted"
            )
        }), 400

    try:
        users = db.metadata.tables["users"]
        assignments = db.metadata.tables["quiz_assignments"]
        classrooms = db.metadata.tables["classrooms"]
        quizzes = db.metadata.tables["teacher_quizzes"]
        recipients = db.metadata.tables[
            "quiz_assignment_recipients"
        ]
        attempts = db.metadata.tables[
            "quiz_assignment_attempts"
        ]

        teacher_id = int(get_jwt_identity())

        teacher = db.session.execute(
            db.select(
                users.c["id"],
                users.c["role"],
            ).where(users.c["id"] == teacher_id)
        ).mappings().first()

        if teacher is None:
            return jsonify({
                "error": "User account no longer exists"
            }), 404

        if teacher["role"] != "teacher":
            return jsonify({
                "error": "Only teachers can view mistake reports"
            }), 403

        assignment = db.session.execute(
            db.select(
                assignments.c["id"],
                assignments.c["deadline_at"],
                classrooms.c["id"].label("classroom_id"),
                classrooms.c["name"].label("classroom_name"),
                quizzes.c["title"].label("quiz_title"),
                quizzes.c["status"].label("quiz_status"),
                quizzes.c["question_count"],
                quizzes.c["questions"],
            )
            .select_from(
                assignments
                .join(
                    classrooms,
                    classrooms.c["id"]
                    == assignments.c["classroom_id"],
                )
                .join(
                    quizzes,
                    quizzes.c["id"]
                    == assignments.c["quiz_id"],
                )
            )
            .where(
                assignments.c["id"] == assignment_id,
                classrooms.c["teacher_id"] == teacher_id,
                quizzes.c["teacher_id"] == teacher_id,
            )
        ).mappings().first()

        if assignment is None:
            return jsonify({
                "error": "Assignment not found"
            }), 404

        if assignment["quiz_status"] != "published":
            return jsonify({
                "error": "The assigned quiz is unavailable."
            }), 409

        try:
            validated = cast(
                dict[str, Any],
                UpdateTeacherQuizSchema(
                    expected_question_count=assignment[
                        "question_count"
                    ],
                ).load({
                    "title": assignment["quiz_title"],
                    "questions": assignment["questions"],
                }),
            )
        except (ValidationError, ValueError, TypeError):
            return jsonify({
                "error": "The saved quiz is invalid."
            }), 409

        questions = validated["questions"]

        # Rank attempts separately:
        # 1. Latest attempt for participation status.
        # 2. Latest submitted attempt for question statistics.
        latest_ranked = (
            db.select(
                attempts.c["student_id"],
                attempts.c["submitted_at"],
                attempts.c["expires_at"],
                db.func.row_number().over(
                    partition_by=attempts.c["student_id"],
                    order_by=(
                        attempts.c["attempt_number"].desc(),
                        attempts.c["id"].desc(),
                    ),
                ).label("position"),
            )
            .where(
                attempts.c["assignment_id"] == assignment_id
            )
            .subquery()
        )

        submitted_ranked = (
            db.select(
                attempts.c["student_id"],
                attempts.c["answers"],
                attempts.c["total_questions"],
                db.func.row_number().over(
                    partition_by=attempts.c["student_id"],
                    order_by=(
                        attempts.c["attempt_number"].desc(),
                        attempts.c["id"].desc(),
                    ),
                ).label("position"),
            )
            .where(
                attempts.c["assignment_id"] == assignment_id,
                attempts.c["submitted_at"].is_not(None),
            )
            .subquery()
        )

        # Saved recipients remain authoritative, including
        # students who subsequently left the class.
        rows = db.session.execute(
            db.select(
                recipients.c["student_id"],
                users.c["name"].label("student_name"),
                latest_ranked.c["student_id"].label(
                    "latest_student_id"
                ),
                latest_ranked.c["submitted_at"],
                latest_ranked.c["expires_at"],
                submitted_ranked.c["student_id"].label(
                    "submitted_student_id"
                ),
                submitted_ranked.c["answers"],
                submitted_ranked.c["total_questions"],
            )
            .select_from(
                recipients
                .join(
                    users,
                    users.c["id"]
                    == recipients.c["student_id"],
                )
                .outerjoin(
                    latest_ranked,
                    db.and_(
                        latest_ranked.c["student_id"]
                        == recipients.c["student_id"],
                        latest_ranked.c["position"] == 1,
                    ),
                )
                .outerjoin(
                    submitted_ranked,
                    db.and_(
                        submitted_ranked.c["student_id"]
                        == recipients.c["student_id"],
                        submitted_ranked.c["position"] == 1,
                    ),
                )
            )
            .where(
                recipients.c["assignment_id"] == assignment_id
            )
            .order_by(recipients.c["student_id"])
        ).mappings().all()

        now = datetime.now(timezone.utc)
        deadline_at = as_utc(assignment["deadline_at"])

        summary = {
            "recipient_count": len(rows),
            "submitted_students": 0,
            "not_started_students": 0,
            "not_submitted_students": 0,
            "in_progress_students": 0,
            "expired_without_submission_students": 0,
        }

        students = []
        submitted_answers = []
        question_ids = {
            question["id"] for question in questions
        }

        for row in rows:
            has_started = row["latest_student_id"] is not None
            has_submitted = (
                row["submitted_student_id"] is not None
            )

            if not has_started:
                latest_status = "not_started"
            elif row["submitted_at"] is not None:
                latest_status = "submitted"
            elif (
                now >= as_utc(row["expires_at"])
                or now >= deadline_at
            ):
                latest_status = "expired"
            else:
                latest_status = "in_progress"

            if has_submitted:
                participation_status = "submitted"
                summary["submitted_students"] += 1

                answers = row["answers"]

                if (
                    row["total_questions"] != len(questions)
                    or not isinstance(answers, dict)
                    or not set(answers).issubset(question_ids)
                    or any(
                        value not in ("A", "B", "C", "D")
                        for value in answers.values()
                    )
                ):
                    return jsonify({
                        "error": (
                            "A saved submission does not match "
                            "the quiz. The report cannot be "
                            "calculated reliably."
                        )
                    }), 409

                submitted_answers.append(answers)

            elif not has_started:
                participation_status = "not_started"
                summary["not_started_students"] += 1

            else:
                participation_status = "not_submitted"
                summary["not_submitted_students"] += 1

                if latest_status == "expired":
                    summary[
                        "expired_without_submission_students"
                    ] += 1
                else:
                    summary["in_progress_students"] += 1

            if (
                status_filter == "all"
                or participation_status == status_filter
            ):
                students.append({
                    "student_id": row["student_id"],
                    "student_name": row["student_name"],
                    "participation_status": participation_status,
                    "latest_attempt_status": latest_status,
                })

        assessed_students = len(submitted_answers)
        question_reports = []

        for index, question in enumerate(questions, start=1):
            correct_count = 0
            wrong_count = 0
            unanswered_count = 0

            for answers in submitted_answers:
                selected_option = answers.get(question["id"])

                if selected_option is None:
                    unanswered_count += 1
                elif selected_option == question["correct_option"]:
                    correct_count += 1
                else:
                    wrong_count += 1

            question_reports.append({
                "id": question["id"],
                "question_number": index,
                "question_text": question["question_text"],
                "correct_option": question["correct_option"],
                "correct_answer": question[
                    f"option_{question['correct_option'].lower()}"
                ],
                "assessed_students": assessed_students,
                "correct_count": correct_count,
                "wrong_count": wrong_count,
                "unanswered_count": unanswered_count,
                "wrong_percentage": (
                    round(
                        wrong_count / assessed_students * 100,
                        2,
                    )
                    if assessed_students
                    else None
                ),
            })

        most_missed = sorted(
            (
                item for item in question_reports
                if item["wrong_count"] > 0
            ),
            key=lambda item: (
                -item["wrong_count"],
                item["question_number"],
            ),
        )

        page_size = 20
        start_index = (page - 1) * page_size

        return jsonify({
            "assignment": {
                "id": assignment["id"],
                "quiz_title": assignment["quiz_title"],
                "classroom_id": assignment["classroom_id"],
                "classroom_name": assignment["classroom_name"],
                "deadline_at": deadline_at.isoformat(),
            },
            "server_time": now.isoformat(),
            "attempt_policy": "latest_submitted_per_student",
            "summary": summary,
            "questions": question_reports,
            "most_missed_question_ids": [
                item["id"] for item in most_missed
            ],
            "students": students[
                start_index:start_index + page_size
            ],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "status": status_filter,
                "total": len(students),
                "has_more": (
                    start_index + page_size < len(students)
                ),
            },
        }), 200

    except SQLAlchemyError:
        db.session.rollback()

        return jsonify({
            "error": (
                "Could not load the mistake report. "
                "Try again later."
            )
        }), 500


@quiz_assignments_bp.patch("/<string:assignment_id>/remove")
@jwt_required()
def remove_student_quiz_assignment(assignment_id):
    student = db.session.get(User, int(get_jwt_identity()))

    if student is None:
        return jsonify({
            "error": "User account no longer exists"
        }), 404

    if student.role != "student":
        return jsonify({
            "error": "Only students can remove their assigned quizzes"
        }), 403

    body = request.get_json(silent=True)

    if not isinstance(body, dict) or body:
        return jsonify({
            "error": "Request body must be an empty JSON object"
        }), 400

    recipients = db.metadata.tables["quiz_assignment_recipients"]

    try:
        recipient = db.session.execute(
            db.select(
                recipients.c["id"],
                recipients.c["removed_at"],
            )
            .where(
                recipients.c["assignment_id"] == assignment_id,
                recipients.c["student_id"] == student.id,
            )
            .with_for_update()
        ).mappings().first()

        if recipient is None:
            db.session.rollback()
            return jsonify({
                "error": "Assignment not found"
            }), 404

        # Preserve the original time when a request is repeated.
        # Preserve the original time when a request is repeated.
        if recipient["removed_at"] is None:
            submitted_attempt_id = db.session.scalar(
                db.select(QuizAssignmentAttempt.id)
                .where(
                    QuizAssignmentAttempt.assignment_id == assignment_id,
                    QuizAssignmentAttempt.student_id == student.id,
                    QuizAssignmentAttempt.submitted_at.is_not(None),
                )
                .limit(1)
            )

            if submitted_attempt_id is None:
                db.session.rollback()

                return jsonify({
                    "error": (
                        "Submit at least one quiz attempt before "
                        "moving this assignment to history."
                    ),
                    "code": "SUBMITTED_ATTEMPT_REQUIRED",
                }), 409

            db.session.execute(
                recipients.update()
                .where(
                    recipients.c["id"] == recipient["id"],
                    recipients.c["removed_at"].is_(None),
                )
                .values(
                    removed_at=datetime.now(timezone.utc),
                )
            )

        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Could not move assignment to history. Try again later."
        }), 500

    return jsonify({
        "message": "Assignment moved to history",
        "assignment_id": assignment_id,
    }), 200