from datetime import datetime, timedelta, timezone
from typing import Any, cast
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from marshmallow import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from models.class_exam import ClassExam
from models.class_exam_result import ClassExamResult
from models.classroom import Classroom
from models.notification import Notification
from models.user import User
from schemas.class_exam_schema import (
    CreateClassExamSchema,
    UpdateClassExamResultsSchema,
)


class_exams_bp = Blueprint(
    "class_exams",
    __name__,
    url_prefix="/api/class-exams",
)

create_exam_schema = CreateClassExamSchema()
update_results_schema = UpdateClassExamResultsSchema()


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def serialize_exam(exam: ClassExam):
    return {
        "id": exam.id,
        "classroom_id": exam.classroom_id,
        "title": exam.title,
        "description": exam.description,
        "total_marks": str(exam.total_marks),
        "starts_at": as_utc(exam.starts_at).isoformat(),
        "ends_at": as_utc(exam.ends_at).isoformat(),
        "timezone_name": exam.timezone_name,
        "results_published_at": (
            as_utc(exam.results_published_at).isoformat()
            if exam.results_published_at is not None
            else None
        ),
        "created_at": as_utc(exam.created_at).isoformat(),
        "updated_at": as_utc(exam.updated_at).isoformat(),
    }


def database_error():
    db.session.rollback()

    return jsonify({
        "error": "Could not complete exam request. Try again later."
    }), 500


@class_exams_bp.post("/classes/<int:classroom_id>")
@jwt_required()
def create_class_exam(classroom_id):
    try:
        user = db.session.get(User, int(get_jwt_identity()))

        if user is None:
            return jsonify({
                "error": "User account no longer exists"
            }), 404

        if user.role != "teacher":
            return jsonify({
                "error": "Only teachers can create class exams"
            }), 403

        classroom = db.session.scalar(
            db.select(Classroom)
            .where(Classroom.id == classroom_id)
            .with_for_update(of=Classroom)
        )

        if classroom is None:
            db.session.rollback()
            return jsonify({"error": "Class not found"}), 404

        if classroom.teacher_id != user.id:
            db.session.rollback()
            return jsonify({
                "error": "You do not own this class"
            }), 403

        body = request.get_json(silent=True)

        if not isinstance(body, dict):
            db.session.rollback()
            return jsonify({
                "error": "Request body must be a JSON object"
            }), 400

        try:
            data = cast(
                dict[str, Any],
                create_exam_schema.load(body),
            )
        except ValidationError as error:
            db.session.rollback()
            return jsonify({
                "error": "Validation failed",
                "messages": error.messages,
            }), 400

        memberships = db.metadata.tables["class_memberships"]
        users = db.metadata.tables["users"]

        student_ids = db.session.scalars(
            db.select(memberships.c["student_id"])
            .join(
                users,
                users.c["id"] == memberships.c["student_id"],
            )
            .where(
                memberships.c["classroom_id"] == classroom_id,
                users.c["role"] == "student",
            )
            .order_by(memberships.c["student_id"])
        ).all()

        if not student_ids:
            db.session.rollback()
            return jsonify({
                "error": "This class has no students to schedule an exam for"
            }), 400

        exam = ClassExam(
            classroom_id=classroom_id,
            title=data["title"],
            description=data["description"],
            total_marks=data["total_marks"],
            starts_at=as_utc(data["starts_at"]),
            ends_at=as_utc(data["ends_at"]),
            timezone_name=data["timezone_name"],
        )

        db.session.add(exam)
        db.session.flush()

        local_start = as_utc(exam.starts_at).astimezone(
            ZoneInfo(exam.timezone_name)
        )
        date_label = local_start.strftime("%d %b %Y, %I:%M %p")

        for student_id in student_ids:
            db.session.add(
                ClassExamResult(
                    exam_id=exam.id,
                    student_id=student_id,
                )
            )

            db.session.add(
                Notification(
                    user_id=student_id,
                    notification_type="class_exam_scheduled",
                    title="New class exam scheduled",
                    message=(
                        f'{classroom.name}: "{exam.title}" starts at '
                        f"{date_label} ({exam.timezone_name}). "
                        f"Total marks: {exam.total_marks}."
                    ),
                )
            )

        # Save the exam, recipient records and notifications together.
        db.session.flush()

        response_body = {
            "message": "Class exam scheduled",
            "exam": serialize_exam(exam),
            "recipient_count": len(student_ids),
        }

        db.session.commit()

        return jsonify(response_body), 201

    except SQLAlchemyError:
        return database_error()

@class_exams_bp.get("")
@jwt_required()
def list_class_exams():
    try:
        user = db.session.get(User, int(get_jwt_identity()))

        if user is None:
            return jsonify({
                "error": "User account no longer exists"
            }), 404

        if user.role not in ("teacher", "student"):
            return jsonify({
                "error": "Only teachers and students can access exams"
            }), 403

        try:
            page = int(request.args.get("page", "1"))

            if not 1 <= page <= 10000:
                raise ValueError

        except ValueError:
            return jsonify({
                "error": "Page must be between 1 and 10000"
            }), 400

        exams_table = db.metadata.tables["class_exams"]
        classrooms_table = db.metadata.tables["classrooms"]
        results_table = db.metadata.tables["class_exam_results"]

        query = (
            db.select(
                ClassExam,
                classrooms_table.c["name"].label("classroom_name"),
            )
            .join(
                Classroom,
                Classroom.id == ClassExam.classroom_id,
            )
        )

        if user.role == "teacher":
            query = query.where(
                classrooms_table.c["teacher_id"] == user.id,
            )
        else:
            is_recipient = (
                db.select(results_table.c["id"])
                .where(
                    results_table.c["exam_id"] == exams_table.c["id"],
                    results_table.c["student_id"] == user.id,
                )
                .correlate(exams_table)
                .exists()
            )

            query = query.where(is_recipient)

        # Calendar callers provide both boundaries.
        has_start = "starts_at" in request.args
        has_end = "ends_at" in request.args

        if has_start or has_end:
            try:
                range_start = datetime.fromisoformat(
                    request.args.get("starts_at", "")
                )
                range_end = datetime.fromisoformat(
                    request.args.get("ends_at", "")
                )

                if (
                    range_start.utcoffset() is None
                    or range_end.utcoffset() is None
                ):
                    raise ValueError

                range_start = as_utc(range_start)
                range_end = as_utc(range_end)

                if (
                    range_end <= range_start
                    or range_end - range_start > timedelta(days=93)
                ):
                    raise ValueError

            except ValueError:
                return jsonify({
                    "error": (
                        "Provide timezone-aware starts_at and ends_at. "
                        "The range must be positive and no longer "
                        "than 93 days."
                    )
                }), 400

            query = query.where(
                exams_table.c["starts_at"] < range_end,
                exams_table.c["ends_at"] > range_start,
            )

        page_size = 20

        rows = db.session.execute(
            query
            .order_by(
                exams_table.c["starts_at"].desc(),
                exams_table.c["id"].desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size + 1)
        ).mappings().all()

        items = []

        for row in rows[:page_size]:
            exam = row["ClassExam"]
            item = serialize_exam(exam)

            item.update({
                "classroom_name": row["classroom_name"],
                "kind": "class_exam",
                "read_only": True,
            })

            items.append(item)

        return jsonify({
            "exams": items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "has_more": len(rows) > page_size,
            },
        }), 200

    except SQLAlchemyError:
        return database_error()


@class_exams_bp.patch("/<string:exam_id>/results")
@jwt_required()
def save_class_exam_results(exam_id):
    try:
        user = db.session.get(User, int(get_jwt_identity()))

        if user is None:
            return jsonify({
                "error": "User account no longer exists"
            }), 404

        if user.role != "teacher":
            return jsonify({
                "error": "Only teachers can enter exam results"
            }), 403

        # Marks saving and publication will lock the same exam record.
        exam = db.session.scalar(
            db.select(ClassExam)
            .where(ClassExam.id == exam_id)
            .with_for_update(of=ClassExam)
        )

        if exam is None:
            db.session.rollback()
            return jsonify({"error": "Exam not found"}), 404

        classroom = db.session.get(Classroom, exam.classroom_id)

        if classroom is None or classroom.teacher_id != user.id:
            db.session.rollback()
            return jsonify({
                "error": "You do not own this exam's class"
            }), 403

        if exam.results_published_at is not None:
            db.session.rollback()
            return jsonify({
                "error": "Published exam results cannot be edited"
            }), 409

        body = request.get_json(silent=True)

        if not isinstance(body, dict):
            db.session.rollback()
            return jsonify({
                "error": "Request body must be a JSON object"
            }), 400

        try:
            data = cast(
                dict[str, Any],
                update_results_schema.load(body),
            )
        except ValidationError as error:
            db.session.rollback()
            return jsonify({
                "error": "Validation failed",
                "messages": error.messages,
            }), 400

        entries = data["results"]
        student_ids = [
            entry["student_id"]
            for entry in entries
        ]

        results_table = db.metadata.tables["class_exam_results"]

        saved_results = db.session.scalars(
            db.select(ClassExamResult).where(
                results_table.c["exam_id"] == exam.id,
                results_table.c["student_id"].in_(student_ids),
            )
        ).all()

        results_by_student = {
            result.student_id: result
            for result in saved_results
        }

        if set(results_by_student) != set(student_ids):
            db.session.rollback()
            return jsonify({
                "error": (
                    "Every student must be a saved recipient "
                    "of this exam"
                )
            }), 400

        # Validate the entire batch before changing any saved marks.
        for entry in entries:
            marks = entry["obtained_marks"]

            if marks is not None and marks > exam.total_marks:
                db.session.rollback()
                return jsonify({
                    "error": (
                        "Obtained marks cannot exceed "
                        "the exam's total marks"
                    )
                }), 400

        now = datetime.now(timezone.utc)

        for entry in entries:
            result = results_by_student[entry["student_id"]]
            result.obtained_marks = entry["obtained_marks"]
            result.is_absent = entry["is_absent"]
            result.updated_at = now

        exam.updated_at = now

        db.session.commit()

        return jsonify({
            "message": "Exam results saved as draft",
            "updated_count": len(entries),
        }), 200

    except SQLAlchemyError:
        return database_error()

@class_exams_bp.post("/<string:exam_id>/publish")
@jwt_required()
def publish_class_exam_results(exam_id):
    try:
        user = db.session.get(User, int(get_jwt_identity()))

        if user is None:
            return jsonify({
                "error": "User account no longer exists"
            }), 404

        if user.role != "teacher":
            return jsonify({
                "error": "Only teachers can publish exam results"
            }), 403

        exam = db.session.scalar(
            db.select(ClassExam)
            .where(ClassExam.id == exam_id)
            .with_for_update(of=ClassExam)
        )

        if exam is None:
            db.session.rollback()
            return jsonify({"error": "Exam not found"}), 404

        classroom = db.session.get(Classroom, exam.classroom_id)

        if classroom is None or classroom.teacher_id != user.id:
            db.session.rollback()
            return jsonify({
                "error": "You do not own this exam's class"
            }), 403

        body = request.get_json(silent=True)

        if not isinstance(body, dict) or body:
            db.session.rollback()
            return jsonify({
                "error": "Send an empty JSON object to publish results"
            }), 400

        # Retrying publication must not send duplicate notifications.
        if exam.results_published_at is not None:
            response_body = {
                "message": "Exam results are already published",
                "exam": serialize_exam(exam),
            }
            db.session.rollback()
            return jsonify(response_body), 200

        results_table = db.metadata.tables["class_exam_results"]

        results = db.session.scalars(
            db.select(ClassExamResult).where(
                results_table.c["exam_id"] == exam.id,
            )
        ).all()

        if not results:
            db.session.rollback()
            return jsonify({
                "error": "This exam has no saved recipients"
            }), 409

        for result in results:
            marks = result.obtained_marks

            if (
                (result.is_absent and marks is not None)
                or (
                    not result.is_absent
                    and (
                        marks is None
                        or marks < 0
                        or marks > exam.total_marks
                    )
                )
            ):
                db.session.rollback()
                return jsonify({
                    "error": (
                        "Enter valid marks or mark absent "
                        "for every student before publishing"
                    )
                }), 409

        now = datetime.now(timezone.utc)
        exam.results_published_at = now
        exam.updated_at = now

        for result in results:
            db.session.add(
                Notification(
                    user_id=result.student_id,
                    notification_type="class_exam_results_published",
                    title="Class exam results published",
                    message=(
                        f'{classroom.name}: results for '
                        f'"{exam.title}" are now available.'
                    ),
                )
            )

        db.session.flush()

        response_body = {
            "message": "Exam results published",
            "exam": serialize_exam(exam),
            "recipient_count": len(results),
        }

        db.session.commit()

        return jsonify(response_body), 200

    except SQLAlchemyError:
        return database_error()

@class_exams_bp.get("/<string:exam_id>/results")
@jwt_required()
def get_class_exam_results_for_teacher(exam_id):
    try:
        user = db.session.get(User, int(get_jwt_identity()))

        if user is None:
            return jsonify({
                "error": "User account no longer exists"
            }), 404

        if user.role != "teacher":
            return jsonify({
                "error": "Only teachers can view the class result list"
            }), 403

        exam = db.session.get(ClassExam, exam_id)

        if exam is None:
            return jsonify({"error": "Exam not found"}), 404

        classroom = db.session.get(Classroom, exam.classroom_id)

        if classroom is None or classroom.teacher_id != user.id:
            return jsonify({
                "error": "You do not own this exam's class"
            }), 403

        try:
            page = int(request.args.get("page", "1"))

            if not 1 <= page <= 10000:
                raise ValueError

        except ValueError:
            return jsonify({
                "error": "Page must be between 1 and 10000"
            }), 400

        results_table = db.metadata.tables["class_exam_results"]
        users_table = db.metadata.tables["users"]
        page_size = 20

        rows = db.session.execute(
            db.select(
                ClassExamResult,
                users_table.c["name"].label("student_name"),
            )
            .join(
                User,
                users_table.c["id"] == results_table.c["student_id"],
            )
            .where(results_table.c["exam_id"] == exam.id)
            .order_by(results_table.c["student_id"])
            .offset((page - 1) * page_size)
            .limit(page_size + 1)
        ).mappings().all()

        items = []

        for row in rows[:page_size]:
            result = row["ClassExamResult"]

            items.append({
                "student_id": result.student_id,
                "student_name": row["student_name"],
                "obtained_marks": (
                    str(result.obtained_marks)
                    if result.obtained_marks is not None
                    else None
                ),
                "is_absent": result.is_absent,
            })

        recipient_count = db.session.scalar(
            db.select(db.func.count())
            .select_from(ClassExamResult)
            .where(results_table.c["exam_id"] == exam.id)
        )

        return jsonify({
            "exam": serialize_exam(exam),
            "classroom_name": classroom.name,
            "recipient_count": recipient_count,
            "results": items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "has_more": len(rows) > page_size,
            },
        }), 200

    except SQLAlchemyError:
        return database_error()


@class_exams_bp.get("/<string:exam_id>/my-result")
@jwt_required()
def get_my_class_exam_result(exam_id):
    try:
        user = db.session.get(User, int(get_jwt_identity()))

        if user is None:
            return jsonify({
                "error": "User account no longer exists"
            }), 404

        if user.role != "student":
            return jsonify({
                "error": "Only students can view their own exam result"
            }), 403

        results_table = db.metadata.tables["class_exam_results"]

        result = db.session.scalar(
            db.select(ClassExamResult).where(
                results_table.c["exam_id"] == exam_id,
                results_table.c["student_id"] == user.id,
            )
        )

        if result is None:
            return jsonify({"error": "Exam not found"}), 404

        exam = db.session.get(ClassExam, exam_id)

        if exam is None:
            return jsonify({"error": "Exam not found"}), 404

        if exam.results_published_at is None:
            return jsonify({
                "error": "Exam results have not been published yet",
                "code": "EXAM_RESULTS_NOT_PUBLISHED",
            }), 409

        classroom = db.session.get(Classroom, exam.classroom_id)

        return jsonify({
            "exam": serialize_exam(exam),
            "classroom_name": (
                classroom.name if classroom is not None else "Class"
            ),
            "result": {
                "obtained_marks": (
                    str(result.obtained_marks)
                    if result.obtained_marks is not None
                    else None
                ),
                "is_absent": result.is_absent,
            },
        }), 200

    except SQLAlchemyError:
        return database_error()