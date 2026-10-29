from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Mapping, NoReturn, cast

from flask import Blueprint, abort, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from marshmallow import Schema, ValidationError
from sqlalchemy import Table, select
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from models.class_membership import ClassMembership
from models.classroom import Classroom
from models.learning_assignment import LearningAssignment
from models.learning_assignment_recipient import (
    LearningAssignmentRecipient,
)
from models.learning_assignment_submission import (
    LearningAssignmentSubmission,
)
from models.notification import Notification
from models.user import User
from schemas.learning_assignment_schema import (
    CreateLearningAssignmentSchema,
    ReviewLearningAssignmentSchema,
    SubmitLearningAssignmentSchema,
)
from services.learning_feedback_service import (
    LearningFeedbackError,
    generate_learning_feedback,
)
from services.learning_reference_service import (
    LearningReferenceError,
    generate_reference_answer,
)

learning_assignments_bp = Blueprint(
    "learning_assignments",
    __name__,
    url_prefix="/api/learning-assignments",
)

create_schema = CreateLearningAssignmentSchema()
submit_schema = SubmitLearningAssignmentSchema()
review_schema = ReviewLearningAssignmentSchema()

PAGE_SIZE = 20


def table_for(model: Any) -> Table:
    return cast(
        Table,
        db.metadata.tables[model.__tablename__],
    )


def reject(message: str, status_code: int) -> NoReturn:
    db.session.rollback()

    response = jsonify({"error": message})
    response.status_code = status_code
    abort(response)


def database_action(
    function: Callable[..., Any],
) -> Callable[..., Any]:
    @wraps(function)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        try:
            return function(*args, **kwargs)
        except ValidationError as error:
            db.session.rollback()

            return jsonify({
                "error": "Validation failed",
                "messages": error.messages,
            }), 400
        except SQLAlchemyError:
            db.session.rollback()

            return jsonify({
                "error": (
                    "Could not complete the assignment request. "
                    "Try again later."
                ),
            }), 500

    return wrapped


def one_row(query: Any) -> dict[str, Any] | None:
    row = db.session.execute(query).mappings().first()

    return dict(row) if row is not None else None


def current_user(
    required_role: str | None = None,
) -> dict[str, Any]:
    users = table_for(User)
    identity = get_jwt_identity()

    try:
        user_id = int(identity)
    except (TypeError, ValueError):
        reject("Invalid user identity", 401)

    user = one_row(
        select(users).where(users.c["id"] == user_id)
    )

    if user is None:
        reject("User account no longer exists", 404)

    if user["role"] not in {"teacher", "student"}:
        reject(
            "Only teachers and students can access assignments",
            403,
        )

    if (
        required_role is not None
        and user["role"] != required_role
    ):
        reject(
            f"Only {required_role}s can perform this action",
            403,
        )

    return user


def load_body(schema: Schema) -> dict[str, Any]:
    body = request.get_json(silent=True)

    if not isinstance(body, dict):
        reject("Request body must be a JSON object", 400)

    return cast(dict[str, Any], schema.load(body))


def as_utc(value: datetime) -> datetime:
    # SQLite test timestamps may lose timezone information.
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None

    return as_utc(value).isoformat()


def requested_page() -> int:
    raw_page = request.args.get("page", "1")

    try:
        page = int(raw_page)
    except ValueError:
        reject("Page must be a positive integer", 400)

    if not 1 <= page <= 10000:
        reject("Page must be between 1 and 10000", 400)

    return page


def pagination(
    page: int,
    row_count: int,
) -> dict[str, Any]:
    return {
        "page": page,
        "page_size": PAGE_SIZE,
        "has_more": row_count > PAGE_SIZE,
    }


def assignment_query() -> Any:
    assignments = table_for(LearningAssignment)
    classrooms = table_for(Classroom)
    users = table_for(User)

    return (
        select(
            assignments,
            classrooms.c["name"].label("classroom_name"),
            classrooms.c["teacher_id"].label("teacher_id"),
            users.c["name"].label("teacher_name"),
        )
        .select_from(
            assignments
            .join(
                classrooms,
                classrooms.c["id"]
                == assignments.c["classroom_id"],
            )
            .join(
                users,
                users.c["id"] == classrooms.c["teacher_id"],
            )
        )
    )


def teacher_assignment(
    assignment_id: str,
    teacher_id: int,
) -> dict[str, Any]:
    assignments = table_for(LearningAssignment)
    classrooms = table_for(Classroom)

    assignment = one_row(
        assignment_query().where(
            assignments.c["id"] == assignment_id,
            classrooms.c["teacher_id"] == teacher_id,
        )
    )

    if assignment is None:
        reject("Assignment not found", 404)

    return assignment


def student_recipient(
    assignment_id: str,
    student_id: int,
    *,
    lock: bool = False,
) -> dict[str, Any]:
    recipients = table_for(LearningAssignmentRecipient)

    query = select(recipients).where(
        recipients.c["assignment_id"] == assignment_id,
        recipients.c["student_id"] == student_id,
    )

    if lock:
        query = query.with_for_update(of=recipients)

    recipient = one_row(query)

    if recipient is None:
        reject("Assignment not found", 404)

    return recipient


def find_assignment(
    assignment_id: str,
) -> dict[str, Any]:
    assignments = table_for(LearningAssignment)

    assignment = one_row(
        assignment_query().where(
            assignments.c["id"] == assignment_id
        )
    )

    if assignment is None:
        reject("Assignment not found", 404)

    return assignment


def serialize_assignment(
    assignment: Mapping[str, Any],
    *,
    include_reference: bool = False,
) -> dict[str, Any]:
    result = {
        "id": assignment["id"],
        "classroom_id": assignment["classroom_id"],
        "classroom_name": assignment["classroom_name"],
        "teacher_name": assignment["teacher_name"],
        "title": assignment["title"],
        "instructions": assignment["instructions"],
        "task_type": assignment["task_type"],
        "audience": assignment["audience"],
        "total_marks": str(assignment["total_marks"]),
        "available_at": timestamp(assignment["available_at"]),
        "deadline_at": timestamp(assignment["deadline_at"]),
        "created_at": timestamp(assignment["created_at"]),
        "updated_at": timestamp(assignment["updated_at"]),
    }

    if include_reference:
        result["reference_answer"] = assignment["reference_answer"]

    return result


def serialize_submission(
    submission: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if submission is None:
        return None

    marks = submission["obtained_marks"]

    return {
        "id": submission["id"],
        "answer_text": submission["answer_text"],
        "code_text": submission["code_text"],
        "submitted_at": timestamp(submission["submitted_at"]),
        "obtained_marks": (
            str(marks) if marks is not None else None
        ),
        "feedback": submission["feedback"],
        "reviewed_at": timestamp(submission["reviewed_at"]),
        "status": (
            "reviewed"
            if submission["reviewed_at"] is not None
            else "submitted"
        ),
    }


def find_submission(
    recipient_id: int,
) -> dict[str, Any] | None:
    submissions = table_for(LearningAssignmentSubmission)

    return one_row(
        select(submissions).where(
            submissions.c["recipient_id"] == recipient_id
        )
    )


@learning_assignments_bp.post("")
@jwt_required()
@database_action
def create_learning_assignment() -> Any:
    teacher = current_user("teacher")
    data = load_body(create_schema)

    classrooms = table_for(Classroom)
    memberships = table_for(ClassMembership)
    users = table_for(User)

    classroom = one_row(
        select(classrooms).where(
            classrooms.c["id"] == data["classroom_id"],
            classrooms.c["teacher_id"] == teacher["id"],
        )
    )

    if classroom is None:
        reject("Class not found", 404)

    if data["deadline_at"] <= datetime.now(timezone.utc):
        reject("Deadline must be in the future.", 400)

    query = (
        select(memberships.c["student_id"])
        .select_from(
            memberships.join(
                users,
                users.c["id"] == memberships.c["student_id"],
            )
        )
        .where(
            memberships.c["classroom_id"] == classroom["id"],
            users.c["role"] == "student",
        )
        .order_by(memberships.c["student_id"])
    )

    if data["audience"] == "selected":
        query = query.where(
            memberships.c["student_id"].in_(
                data["student_ids"]
            )
        )

    student_ids = [
        int(student_id)
        for student_id in db.session.execute(
            query.with_for_update(of=memberships)
        ).scalars().all()
    ]

    if (
        data["audience"] == "selected"
        and set(student_ids) != set(data["student_ids"])
    ):
        reject(
            "Every selected student must be a current member "
            "of this class.",
            400,
        )

    if not student_ids:
        reject(
            "No enrolled students are available for this assignment.",
            400,
        )

    # Classic Flask-SQLAlchemy models have dynamic instance attributes.
    assignment = cast(
        Any,
        LearningAssignment(
            classroom_id=classroom["id"],
            title=data["title"],
            instructions=data["instructions"],
            reference_answer=data["reference_answer"],
            task_type=data["task_type"],
            audience=data["audience"],
            total_marks=data["total_marks"],
            available_at=data["available_at"],
            deadline_at=data["deadline_at"],
        ),
    )

    db.session.add(assignment)
    db.session.flush()

    assignment_id = str(assignment.id)

    for student_id in student_ids:
        db.session.add(
            LearningAssignmentRecipient(
                assignment_id=assignment_id,
                student_id=student_id,
            )
        )

        db.session.add(
            Notification(
                user_id=student_id,
                notification_type="learning_assignment",
                title="New learning assignment",
                message=(
                    f'{teacher["name"]} assigned "{data["title"]}" '
                    f'to you in "{classroom["name"]}".'
                ),
            )
        )

    result = serialize_assignment(
        find_assignment(assignment_id)
    )
    result["recipient_count"] = len(student_ids)

    # Save assignment, recipients and notifications together.
    db.session.commit()

    return jsonify({
        "message": "Learning assignment created successfully",
        "assignment": result,
    }), 201


@learning_assignments_bp.get("")
@jwt_required()
@database_action
def list_learning_assignments() -> Any:
    user = current_user()
    page = requested_page()

    assignments = table_for(LearningAssignment)
    classrooms = table_for(Classroom)
    recipients = table_for(LearningAssignmentRecipient)

    query = assignment_query()

    if user["role"] == "teacher":
        query = query.where(
            classrooms.c["teacher_id"] == user["id"]
        )
    else:
        is_recipient = (
            select(recipients.c["id"])
            .where(
                recipients.c["assignment_id"]
                == assignments.c["id"],
                recipients.c["student_id"] == user["id"],
            )
            .correlate(assignments)
            .exists()
        )

        query = query.where(is_recipient)

    rows = db.session.execute(
        query
        .order_by(
            assignments.c["created_at"].desc(),
            assignments.c["id"].desc(),
        )
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE + 1)
    ).mappings().all()

    return jsonify({
        "assignments": [
            serialize_assignment(dict(row))
            for row in rows[:PAGE_SIZE]
        ],
        "pagination": pagination(page, len(rows)),
        "server_time": timestamp(datetime.now(timezone.utc)),
    }), 200


@learning_assignments_bp.get("/<string:assignment_id>")
@jwt_required()
@database_action
def get_learning_assignment(assignment_id: str) -> Any:
    user = current_user()
    recipient = None

    if user["role"] == "teacher":
        assignment = teacher_assignment(
            assignment_id,
            user["id"],
        )
    else:
        recipient = student_recipient(
            assignment_id,
            user["id"],
        )
        assignment = find_assignment(assignment_id)

    submission = (
        find_submission(recipient["id"])
        if recipient is not None
        else None
    )

    now = datetime.now(timezone.utc)

    return jsonify({
        "assignment": serialize_assignment(assignment),
        "submission": serialize_submission(submission),
        "can_submit": (
            user["role"] == "student"
            and submission is None
            and as_utc(assignment["available_at"]) <= now
            and now < as_utc(assignment["deadline_at"])
        ),
        "server_time": timestamp(now),
    }), 200


@learning_assignments_bp.post(
    "/<string:assignment_id>/submit"
)
@jwt_required()
@database_action
def submit_learning_assignment(assignment_id: str) -> Any:
    student = current_user("student")
    data = load_body(submit_schema)

    # Lock the saved recipient to serialize duplicate submissions.
    recipient = student_recipient(
        assignment_id,
        student["id"],
        lock=True,
    )

    assignment = find_assignment(assignment_id)

    if find_submission(recipient["id"]) is not None:
        reject("You have already submitted this assignment.", 409)

    now = datetime.now(timezone.utc)

    if now < as_utc(assignment["available_at"]):
        reject("This assignment is not available yet.", 409)

    if now >= as_utc(assignment["deadline_at"]):
        reject("The assignment deadline has passed.", 409)

    submission = cast(
        Any,
        LearningAssignmentSubmission(
            recipient_id=recipient["id"],
            answer_text=data["answer_text"],
            code_text=data["code_text"],
        ),
    )
    submission.submitted_at = now

    db.session.add(submission)
    db.session.flush()

    result = serialize_submission(
        find_submission(recipient["id"])
    )

    db.session.commit()

    return jsonify({
        "message": "Assignment submitted successfully",
        "submission": result,
    }), 201


@learning_assignments_bp.get(
    "/<string:assignment_id>/submissions"
)
@jwt_required()
@database_action
def list_learning_assignment_submissions(
    assignment_id: str,
) -> Any:
    teacher = current_user("teacher")
    page = requested_page()

    assignment = teacher_assignment(
        assignment_id,
        teacher["id"],
    )

    recipients = table_for(LearningAssignmentRecipient)
    submissions = table_for(LearningAssignmentSubmission)
    users = table_for(User)

    rows = db.session.execute(
        select(
            recipients.c["student_id"].label(
                "assigned_student_id"
            ),
            users.c["name"].label("student_name"),
            submissions,
        )
        .select_from(
            recipients
            .join(
                users,
                users.c["id"] == recipients.c["student_id"],
            )
            .outerjoin(
                submissions,
                submissions.c["recipient_id"]
                == recipients.c["id"],
            )
        )
        .where(
            recipients.c["assignment_id"] == assignment_id
        )
        .order_by(recipients.c["student_id"])
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE + 1)
    ).mappings().all()

    students = []

    for row in rows[:PAGE_SIZE]:
        submission = (
            serialize_submission(dict(row))
            if row["id"] is not None
            else None
        )
        if submission is not None:
            submission["ai_feedback"] = row["ai_feedback"]
            submission["ai_feedback_generated_at"] = timestamp(
                row["ai_feedback_generated_at"]
            )

        students.append({
            "student_id": row["assigned_student_id"],
            "student_name": row["student_name"],
            "status": (
                submission["status"]
                if submission is not None
                else "not_submitted"
            ),
            "submission": submission,
        })

    return jsonify({
        "assignment": serialize_assignment(
            assignment,
            include_reference=True,
        ),
        "students": students,
        "pagination": pagination(page, len(rows)),
    }), 200


@learning_assignments_bp.patch(
    "/<string:assignment_id>/submissions/"
    "<int:submission_id>/review"
)
@jwt_required()
@database_action
def review_learning_assignment(
    assignment_id: str,
    submission_id: int,
) -> Any:
    teacher = current_user("teacher")
    data = load_body(review_schema)

    assignment = teacher_assignment(
        assignment_id,
        teacher["id"],
    )

    recipients = table_for(LearningAssignmentRecipient)
    submissions = table_for(LearningAssignmentSubmission)

    row = one_row(
        select(
            submissions,
            recipients.c["student_id"].label("student_id"),
        )
        .select_from(
            submissions.join(
                recipients,
                recipients.c["id"]
                == submissions.c["recipient_id"],
            )
        )
        .where(
            submissions.c["id"] == submission_id,
            recipients.c["assignment_id"] == assignment_id,
        )
        .with_for_update(of=submissions)
    )

    if row is None:
        reject("Submission not found", 404)

    if data["obtained_marks"] > assignment["total_marks"]:
        reject(
            "Obtained marks cannot exceed the assignment total marks.",
            400,
        )

    if row["reviewed_at"] is not None:
        reject("This submission has already been reviewed.", 409)

    now = datetime.now(timezone.utc)

    db.session.execute(
        submissions.update()
        .where(submissions.c["id"] == submission_id)
        .values(
            obtained_marks=data["obtained_marks"],
            feedback=data["feedback"],
            reviewed_by=teacher["id"],
            reviewed_at=now,
        )
    )

    db.session.add(
        Notification(
            user_id=row["student_id"],
            notification_type="learning_assignment_review",
            title="Assignment reviewed",
            message=(
                f'{teacher["name"]} reviewed "{assignment["title"]}". '
                "Open your learning assignment to see marks and feedback."
            ),
        )
    )

    result = serialize_submission(
        find_submission(row["recipient_id"])
    )

    db.session.commit()

    return jsonify({
        "message": "Submission reviewed successfully",
        "submission": result,
    }), 200
@learning_assignments_bp.post(
    "/<string:assignment_id>/submissions/"
    "<int:submission_id>/ai-feedback"
)
@jwt_required()
@database_action
def create_learning_assignment_ai_feedback(
    assignment_id: str,
    submission_id: int,
) -> Any:
    teacher = current_user("teacher")
    teacher_id = teacher["id"]

    body = request.get_json(silent=True)

    if not isinstance(body, dict):
        reject("Request body must be a JSON object", 400)

    if set(body) - {"response_language"}:
        reject("Unexpected request fields", 400)

    response_language = body.get("response_language", "banglish")

    if (
        not isinstance(response_language, str)
        or response_language not in {"banglish", "english"}
    ):
        reject(
            "Response language must be banglish or english.",
            400,
        )

    assignment = teacher_assignment(assignment_id, teacher_id)

    if assignment["task_type"] != "written":
        reject(
            "AI feedback is available only for written assignments.",
            400,
        )

    if not assignment["reference_answer"].strip():
        reject(
            "A teacher reference answer is required for AI feedback.",
            400,
        )

    recipients = table_for(LearningAssignmentRecipient)
    submissions = table_for(LearningAssignmentSubmission)

    submission_query = (
        select(submissions)
        .select_from(
            submissions.join(
                recipients,
                recipients.c["id"] == submissions.c["recipient_id"],
            )
        )
        .where(
            submissions.c["id"] == submission_id,
            recipients.c["assignment_id"] == assignment_id,
        )
    )

    row = one_row(submission_query)

    if row is None:
        reject("Submission not found", 404)

    if row["ai_feedback"] is not None:
        return jsonify({
            "ai_feedback": row["ai_feedback"],
            "ai_feedback_generated_at": timestamp(
                row["ai_feedback_generated_at"]
            ),
            "cached": True,
        }), 200

    if row["reviewed_at"] is not None:
        reject("This submission has already been reviewed.", 409)

    if not row["answer_text"].strip():
        reject(
            "A written student answer is required for AI feedback.",
            400,
        )

    original_title = assignment["title"]
    original_instructions = assignment["instructions"]
    original_reference = assignment["reference_answer"]
    original_answer = row["answer_text"]

    # Release the database transaction before the external API call.
    db.session.rollback()

    try:
        feedback = generate_learning_feedback(
            title=original_title,
            instructions=original_instructions,
            reference_answer=original_reference,
            answer_text=original_answer,
            response_language=response_language,
        )
    except LearningFeedbackError as error:
        reject(str(error), error.status_code)

    # Recheck the account and ownership after waiting for Maira.
    teacher = current_user("teacher")
    assignment = teacher_assignment(
        assignment_id,
        teacher["id"],
    )

    row = one_row(
        submission_query.with_for_update(of=submissions)
    )

    if row is None:
        reject("Submission not found", 404)

    # Another request may already have saved a draft.
    if row["ai_feedback"] is not None:
        result = {
            "ai_feedback": row["ai_feedback"],
            "ai_feedback_generated_at": timestamp(
                row["ai_feedback_generated_at"]
            ),
            "cached": True,
        }
        db.session.rollback()
        return jsonify(result), 200

    if row["reviewed_at"] is not None:
        reject(
            "The submission was reviewed while AI feedback was generating.",
            409,
        )

    if (
        assignment["task_type"] != "written"
        or assignment["title"] != original_title
        or assignment["instructions"] != original_instructions
        or assignment["reference_answer"] != original_reference
        or row["answer_text"] != original_answer
    ):
        reject(
            "The assignment or answer changed. Generate feedback again.",
            409,
        )

    now = datetime.now(timezone.utc)

    db.session.execute(
        submissions.update()
        .where(submissions.c["id"] == submission_id)
        .values(
            ai_feedback=feedback,
            ai_feedback_generated_at=now,
        )
    )

    db.session.commit()

    return jsonify({
        "ai_feedback": feedback,
        "ai_feedback_generated_at": timestamp(now),
        "cached": False,
    }), 200

@learning_assignments_bp.post("/reference-answer")
@jwt_required()
@database_action
def create_learning_assignment_reference_answer() -> Any:
    current_user("teacher")

    body = request.get_json(silent=True)

    if not isinstance(body, dict):
        reject("Request body must be a JSON object.", 400)

    allowed_fields = {
        "title",
        "instructions",
        "academic_level",
        "response_language",
    }

    if set(body) - allowed_fields:
        reject("Unexpected request fields.", 400)

    title = body.get("title")
    instructions = body.get("instructions")
    academic_level = body.get("academic_level")
    response_language = body.get("response_language", "banglish")

    if (
        not isinstance(title, str)
        or not 3 <= len(title.strip()) <= 150
    ):
        reject("Title must contain 3 to 150 characters.", 400)

    if (
        not isinstance(instructions, str)
        or not 1 <= len(instructions.strip()) <= 10000
    ):
        reject(
            "Instructions must contain 1 to 10000 characters.",
            400,
        )

    if (
        not isinstance(academic_level, str)
        or academic_level not in {"ssc", "hsc"}
    ):
        reject("Academic level must be ssc or hsc.", 400)

    if (
        not isinstance(response_language, str)
        or response_language not in {"banglish", "english"}
    ):
        reject(
            "Response language must be banglish or english.",
            400,
        )

    # Release the database transaction before calling Maira.
    db.session.rollback()

    try:
        reference_answer = generate_reference_answer(
            title=title.strip(),
            instructions=instructions.strip(),
            academic_level=academic_level,
            response_language=response_language,
        )
    except LearningReferenceError as error:
        reject(str(error), error.status_code)

    # Confirm the account still has teacher access after the API call.
    current_user("teacher")
    db.session.rollback()

    return jsonify({
        "reference_answer": reference_answer,
        "is_draft": True,
    }), 200