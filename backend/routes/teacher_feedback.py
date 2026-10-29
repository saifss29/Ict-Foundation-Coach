from typing import cast

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from marshmallow import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from models.class_membership import ClassMembership
from models.classroom import Classroom
from models.notification import Notification
from models.quiz_attempt import QuizAttempt
from models.teacher_feedback import TeacherFeedback
from models.user import User
from schemas.teacher_feedback_schema import CreateTeacherFeedbackSchema


teacher_feedback_bp = Blueprint(
    "teacher_feedback",
    __name__,
    url_prefix="/api/feedback",
)

create_feedback_schema = CreateTeacherFeedbackSchema()


def get_current_user():
    return db.session.get(User, int(get_jwt_identity()))


def check_teacher_access(user, classroom_id, student_id):
    if user is None:
        return jsonify({
            "error": "User account no longer exists"
        }), 404

    if user.role != "teacher":
        return jsonify({
            "error": "Only teachers can access class feedback"
        }), 403

    classroom = db.session.get(Classroom, classroom_id)

    if classroom is None:
        return jsonify({
            "error": "Class not found"
        }), 404

    if classroom.teacher_id != user.id:
        return jsonify({
            "error": "You do not own this class"
        }), 403

    membership = db.session.scalar(
        db.select(ClassMembership.id).where(
            ClassMembership.classroom_id == classroom_id,
            ClassMembership.student_id == student_id,
        )
    )

    if membership is None:
        return jsonify({
            "error": "Student is not a member of this class"
        }), 404

    student = db.session.get(User, student_id)

    if student is None or student.role != "student":
        return jsonify({
            "error": "Student not found"
        }), 404

    return None


def serialize_feedback(feedback, teacher_name, classroom_name):
    return {
        "id": feedback.id,
        "classroom_id": feedback.classroom_id,
        "classroom_name": classroom_name,
        "teacher_id": feedback.teacher_id,
        "teacher_name": teacher_name,
        "student_id": feedback.student_id,
        "attempt_id": feedback.attempt_id,
        "message": feedback.message,
        "created_at": feedback.created_at.isoformat(),
    }


def feedback_list_response(*conditions):
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

    users_table = db.metadata.tables["users"]
    classrooms_table = db.metadata.tables["classrooms"]

    query = (
        db.select(
            TeacherFeedback,
            users_table.c["name"].label("teacher_name"),
            classrooms_table.c["name"].label("classroom_name"),
        )
        .join(User, User.id == TeacherFeedback.teacher_id)
        .join(
            Classroom,
            Classroom.id == TeacherFeedback.classroom_id,
        )
        .where(*conditions)
        .order_by(
            db.desc(TeacherFeedback.created_at),
            db.desc(TeacherFeedback.id),
        )
        .offset((page - 1) * page_size)
        .limit(page_size + 1)
    )

    rows = db.session.execute(query).mappings().all()

    feedback_items = [
        serialize_feedback(
            row["TeacherFeedback"],
            row["teacher_name"],
            row["classroom_name"],
        )
        for row in rows[:page_size]
    ]

    return jsonify({
        "feedback": feedback_items,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "has_more": len(rows) > page_size,
        },
    }), 200


@teacher_feedback_bp.post(
    "/classes/<int:classroom_id>/students/<int:student_id>"
)
@jwt_required()
def create_teacher_feedback(classroom_id, student_id):
    user = get_current_user()

    if user is None:
        return jsonify({
            "error": "User account no longer exists"
        }), 404

    access_error = check_teacher_access(
        user,
        classroom_id,
        student_id,
    )

    if access_error is not None:
        return access_error

    request_data = request.get_json(silent=True)

    if not isinstance(request_data, dict):
        return jsonify({
            "error": "Request body must be a JSON object"
        }), 400

    request_data = request_data.copy()

    if isinstance(request_data.get("message"), str):
        request_data["message"] = request_data["message"].strip()

    try:
        data = cast(
            dict[str, str | int | None],
            create_feedback_schema.load(request_data),
        )
    except ValidationError as error:
        return jsonify({
            "error": "Validation failed",
            "messages": error.messages,
        }), 400

    attempt_id = cast(int | None, data["attempt_id"])

    if attempt_id is not None:
        attempt = db.session.scalar(
            db.select(QuizAttempt).where(
                QuizAttempt.id == attempt_id,
                QuizAttempt.user_id == student_id,
            )
        )

        if attempt is None:
            return jsonify({
                "error": "Quiz attempt not found for this student"
            }), 404

    feedback = TeacherFeedback(
        classroom_id=classroom_id,
        teacher_id=user.id,
        student_id=student_id,
        message=cast(str, data["message"]),
        attempt_id=attempt_id,
    )

    try:
        db.session.add(feedback)

        # Obtain the feedback ID without committing the transaction.
        db.session.flush()

        notification = Notification(
            user_id=student_id,
            notification_type="teacher_feedback",
            title="New teacher feedback",
            message=f"{user.name} sent you learning feedback.",
            feedback_id=feedback.id,
        )

        db.session.add(notification)

        # Commit the feedback and notification together.
        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Could not save feedback. Try again later."
        }), 500

    classroom = db.session.get(Classroom, classroom_id)

    return jsonify({
        "message": "Feedback sent successfully",
        "feedback": serialize_feedback(
            feedback,
            user.name,
            classroom.name if classroom is not None else "Class",
        ),
    }), 201


@teacher_feedback_bp.get(
    "/classes/<int:classroom_id>/students/<int:student_id>"
)
@jwt_required()
def list_student_feedback_for_teacher(classroom_id, student_id):
    user = get_current_user()

    if user is None:
        return jsonify({
            "error": "User account no longer exists"
        }), 404

    access_error = check_teacher_access(
        user,
        classroom_id,
        student_id,
    )

    if access_error is not None:
        return access_error

    return feedback_list_response(
        TeacherFeedback.classroom_id == classroom_id,
        TeacherFeedback.student_id == student_id,
        TeacherFeedback.teacher_id == user.id,
    )


@teacher_feedback_bp.get("/me")
@jwt_required()
def list_my_feedback():
    user = get_current_user()

    if user is None:
        return jsonify({
            "error": "User account no longer exists"
        }), 404

    if user.role != "student":
        return jsonify({
            "error": "Only students can view their received feedback"
        }), 403

    # Students retain their received feedback after leaving a class.
    return feedback_list_response(
        TeacherFeedback.student_id == user.id,
    )