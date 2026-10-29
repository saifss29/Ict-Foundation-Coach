import secrets
import string
from typing import cast

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from extensions import db
from models.class_membership import ClassMembership
from models.classroom import Classroom
from models.quiz_attempt import QuizAttempt
from models.topic import Topic
from models.user import User
from schemas.classroom_schema import (
    CreateClassroomSchema,
    JoinClassroomSchema,
)


classrooms_bp = Blueprint(
    "classrooms",
    __name__,
    url_prefix="/api/classes",
)

create_classroom_schema = CreateClassroomSchema()
join_classroom_schema = JoinClassroomSchema()

JOIN_CODE_ALPHABET = string.ascii_uppercase + string.digits


def get_current_user():
    return db.session.get(User, int(get_jwt_identity()))


def serialize_classroom(classroom, *, include_join_code=False):
    teacher = db.session.get(User, classroom.teacher_id)

    data = {
        "id": classroom.id,
        "name": classroom.name,
        "teacher_id": classroom.teacher_id,
        "teacher_name": teacher.name if teacher is not None else "Teacher",
        "created_at": classroom.created_at.isoformat(),
    }

    if include_join_code:
        data["join_code"] = classroom.join_code

    return data


def percentage_for_attempt(attempt):
    return round(attempt.score / attempt.total_questions * 100)


@classrooms_bp.post("")
@jwt_required()
def create_classroom():
    user = get_current_user()

    if user is None:
        return jsonify({"error": "User account no longer exists"}), 404

    if user.role != "teacher":
        return jsonify({"error": "Only teachers can create classes"}), 403

    request_data = request.get_json(silent=True)

    if not isinstance(request_data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    # Trim before validation so spaces alone cannot become a class name.
    request_data = request_data.copy()

    if isinstance(request_data.get("name"), str):
        request_data["name"] = request_data["name"].strip()

    try:
        data = cast(
            dict[str, str],
            create_classroom_schema.load(request_data),
        )
    except ValidationError as error:
        return jsonify({
            "error": "Validation failed",
            "messages": error.messages,
        }), 400

    # Retry if a generated code conflicts with an existing unique code.
    for _ in range(3):
        join_code = "".join(
            secrets.choice(JOIN_CODE_ALPHABET)
            for _ in range(8)
        )

        classroom = Classroom(
            name=data["name"],
            teacher_id=user.id,
            join_code=join_code,
        )

        db.session.add(classroom)

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()

            existing_code = db.session.scalar(
                db.select(Classroom.id).where(
                    Classroom.join_code == join_code
                )
            )

            if existing_code is not None:
                continue

            return jsonify({"error": "Could not create class"}), 500

        return jsonify({
            "message": "Class created successfully",
            "classroom": serialize_classroom(
                classroom,
                include_join_code=True,
            ),
        }), 201

    return jsonify({
        "error": "Could not generate a unique class code. Please try again."
    }), 503


@classrooms_bp.get("")
@jwt_required()
def list_my_classes():
    user = get_current_user()

    if user is None:
        return jsonify({"error": "User account no longer exists"}), 404

    if user.role == "teacher":
        query = db.select(Classroom).where(
            Classroom.teacher_id == user.id
        )
    elif user.role == "student":
        query = (
            db.select(Classroom)
            .join(
                ClassMembership,
                ClassMembership.classroom_id == Classroom.id,
            )
            .where(ClassMembership.student_id == user.id)
        )
    else:
        return jsonify({"error": "Account role is not supported"}), 403

    classrooms = db.session.scalars(
        query.order_by(
            Classroom.created_at.desc(),  # pyright: ignore[reportAttributeAccessIssue]
            Classroom.id.desc(),  # pyright: ignore[reportAttributeAccessIssue]
        )
    ).all()

    return jsonify({
        "classes": [
            serialize_classroom(
                classroom,
                include_join_code=user.role == "teacher",
            )
            for classroom in classrooms
        ],
    }), 200


@classrooms_bp.get("/<int:classroom_id>")
@jwt_required()
def get_classroom_details(classroom_id):
    user = get_current_user()

    if user is None:
        return jsonify({"error": "User account no longer exists"}), 404

    if user.role != "teacher":
        return jsonify({
            "error": "Only teachers can view class analytics"
        }), 403

    classroom = db.session.get(Classroom, classroom_id)

    if classroom is None:
        return jsonify({"error": "Class not found"}), 404

    # A teacher must never see another teacher's student data.
    if classroom.teacher_id != user.id:
        return jsonify({"error": "You do not own this class"}), 403

    memberships = db.session.scalars(
        db.select(ClassMembership)
        .where(ClassMembership.classroom_id == classroom.id)
        .order_by(
            ClassMembership.joined_at.asc()  # pyright: ignore[reportAttributeAccessIssue]
        )
    ).all()

    student_ids = [
        membership.student_id
        for membership in memberships
    ]

    students_by_id = {}

    if student_ids:
        students = db.session.scalars(
            db.select(User)
            .where(
                User.id.in_(student_ids)  # pyright: ignore[reportAttributeAccessIssue]
            )
            .order_by(
                User.name.asc()  # pyright: ignore[reportAttributeAccessIssue]
            )
        ).all()

        students_by_id = {
            student.id: student
            for student in students
        }

    attempts = []

    if student_ids:
        attempts = db.session.scalars(
            db.select(QuizAttempt)
            .where(
                QuizAttempt.user_id.in_(student_ids)  # pyright: ignore[reportAttributeAccessIssue]
            )
            .order_by(
                QuizAttempt.completed_at.desc()  # pyright: ignore[reportAttributeAccessIssue]
            )
        ).all()

    topics = db.session.scalars(
        db.select(Topic)
    ).all()

    topics_by_id = {
        topic.id: topic
        for topic in topics
    }

    attempts_by_student = {}

    for attempt in attempts:
        attempts_by_student.setdefault(
            attempt.user_id,
            [],
        ).append(attempt)

    student_data = []

    for membership in memberships:
        student = students_by_id.get(membership.student_id)

        if student is None:
            continue

        student_attempts = attempts_by_student.get(student.id, [])
        latest_attempt = (
            student_attempts[0]
            if student_attempts
            else None
        )

        # Attempts are newest first, so the first attempt per topic
        # represents the student's current result for that topic.
        latest_attempt_by_topic = {}

        for attempt in student_attempts:
            if attempt.topic_id not in latest_attempt_by_topic:
                latest_attempt_by_topic[attempt.topic_id] = attempt

        weakest_topic = None

        if latest_attempt_by_topic:
            weakest_attempt = min(
                latest_attempt_by_topic.values(),
                key=lambda attempt: (
                    attempt.score / attempt.total_questions
                ),
            )

            topic = topics_by_id.get(weakest_attempt.topic_id)

            if topic is not None:
                weakest_topic = {
                    "title": topic.title,
                    "slug": topic.slug,
                    "percentage": percentage_for_attempt(
                        weakest_attempt
                    ),
                }

        student_data.append({
            "id": student.id,
            "name": student.name,
            "email": student.email,
            "joined_at": membership.joined_at.isoformat(),
            "total_attempts": len(student_attempts),
            "latest_score": (
                latest_attempt.score
                if latest_attempt
                else None
            ),
            "latest_total_questions": (
                latest_attempt.total_questions
                if latest_attempt
                else None
            ),
            "latest_percentage": (
                percentage_for_attempt(latest_attempt)
                if latest_attempt
                else None
            ),
            "last_quiz_at": (
                latest_attempt.completed_at.isoformat()
                if latest_attempt
                else None
            ),
            "weakest_topic": weakest_topic,
        })

    students_started_learning = sum(
        student["total_attempts"] > 0
        for student in student_data
    )

    latest_percentages = [
        student["latest_percentage"]
        for student in student_data
        if student["latest_percentage"] is not None
    ]

    class_average_latest_percentage = None

    if latest_percentages:
        class_average_latest_percentage = round(
            sum(latest_percentages) / len(latest_percentages)
        )

    return jsonify({
        "classroom": serialize_classroom(
            classroom,
            include_join_code=True,
        ),
        "summary": {
            "student_count": len(student_data),
            "students_started_learning": students_started_learning,
            "total_quiz_attempts": len(attempts),
            "class_average_latest_percentage": (
                class_average_latest_percentage
            ),
        },
        "students": student_data,
    }), 200


@classrooms_bp.get(
    "/<int:classroom_id>/students/<int:student_id>/attempts"
)
@jwt_required()
def get_student_attempt_history(classroom_id, student_id):
    user = get_current_user()

    if user is None:
        return jsonify({"error": "User account no longer exists"}), 404

    if user.role != "teacher":
        return jsonify({
            "error": "Only teachers can view student attempt history"
        }), 403

    classroom = db.session.get(Classroom, classroom_id)

    if classroom is None:
        return jsonify({"error": "Class not found"}), 404

    if classroom.teacher_id != user.id:
        return jsonify({"error": "You do not own this class"}), 403

    membership = db.session.scalar(
        db.select(ClassMembership).where(
            ClassMembership.classroom_id == classroom.id,
            ClassMembership.student_id == student_id,
        )
    )

    if membership is None:
        return jsonify({
            "error": "Student is not a member of this class"
        }), 404

    student = db.session.get(User, student_id)

    if student is None or student.role != "student":
        return jsonify({"error": "Student not found"}), 404

    attempts = db.session.scalars(
        db.select(QuizAttempt)
        .where(QuizAttempt.user_id == student.id)
        .order_by(
            QuizAttempt.completed_at.desc()  # pyright: ignore[reportAttributeAccessIssue]
        )
    ).all()

    topics = db.session.scalars(
        db.select(Topic)
    ).all()

    topics_by_id = {
        topic.id: topic
        for topic in topics
    }

    return jsonify({
        "classroom": {
            "id": classroom.id,
            "name": classroom.name,
        },
        "student": {
            "id": student.id,
            "name": student.name,
            "email": student.email,
            "joined_at": membership.joined_at.isoformat(),
        },
        "attempts": [
            {
                "id": attempt.id,
                "topic": (
                    topics_by_id[attempt.topic_id].title
                    if attempt.topic_id in topics_by_id
                    else "Deleted topic"
                ),
                "topic_slug": (
                    topics_by_id[attempt.topic_id].slug
                    if attempt.topic_id in topics_by_id
                    else None
                ),
                "score": attempt.score,
                "total_questions": attempt.total_questions,
                "percentage": percentage_for_attempt(attempt),
                "completed_at": attempt.completed_at.isoformat(),
            }
            for attempt in attempts
        ],
    }), 200


@classrooms_bp.post("/join")
@jwt_required()
def join_classroom():
    user = get_current_user()

    if user is None:
        return jsonify({"error": "User account no longer exists"}), 404

    if user.role != "student":
        return jsonify({"error": "Only students can join classes"}), 403

    request_data = request.get_json(silent=True)

    if not isinstance(request_data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    request_data = request_data.copy()

    if isinstance(request_data.get("join_code"), str):
        request_data["join_code"] = (
            request_data["join_code"].strip().upper()
        )

    try:
        data = cast(
            dict[str, str],
            join_classroom_schema.load(request_data),
        )
    except ValidationError as error:
        return jsonify({
            "error": "Validation failed",
            "messages": error.messages,
        }), 400

    classroom = db.session.scalar(
        db.select(Classroom).where(
            Classroom.join_code == data["join_code"]
        )
    )

    if classroom is None:
        return jsonify({"error": "Class code is invalid"}), 404

    existing_membership = db.session.scalar(
        db.select(ClassMembership.id).where(
            ClassMembership.classroom_id == classroom.id,
            ClassMembership.student_id == user.id,
        )
    )

    if existing_membership is not None:
        return jsonify({
            "error": "You have already joined this class"
        }), 409

    membership = ClassMembership(
        classroom_id=classroom.id,
        student_id=user.id,
    )

    db.session.add(membership)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()

        existing_membership = db.session.scalar(
            db.select(ClassMembership.id).where(
                ClassMembership.classroom_id == classroom.id,
                ClassMembership.student_id == user.id,
            )
        )

        if existing_membership is not None:
            return jsonify({
                "error": "You have already joined this class"
            }), 409

        return jsonify({"error": "Could not join class"}), 500

    return jsonify({
        "message": "Joined class successfully",
        "classroom": serialize_classroom(classroom),
    }), 201


@classrooms_bp.delete("/<int:classroom_id>/membership")
@jwt_required()
def leave_classroom(classroom_id):
    user = get_current_user()

    if user is None:
        return jsonify({"error": "User account no longer exists"}), 404

    if user.role != "student":
        return jsonify({"error": "Only students can leave classes"}), 403

    try:
        # Remove only the authenticated student's membership.
        membership = db.session.scalar(
            db.select(ClassMembership).where(
                ClassMembership.classroom_id == classroom_id,
                ClassMembership.student_id == user.id,
            )
        )

        if membership is None:
            return jsonify({"error": "Class membership not found"}), 404

        db.session.delete(membership)
        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Could not leave class. Try again later."
        }), 500

    return jsonify({
        "message": "Left class successfully"
    }), 200