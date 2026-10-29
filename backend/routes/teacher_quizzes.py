from datetime import datetime, timezone
from typing import cast

from flask import Blueprint, abort, jsonify, make_response, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from marshmallow import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from models.teacher_quiz import TeacherQuiz
from models.topic import Topic
from models.user import User
from schemas.teacher_quiz_schema import (
    CreateTeacherQuizSchema,
    UpdateTeacherQuizSchema,
)
from services.quiz_generator import QuizGenerationError, generate_quiz


teacher_quizzes_bp = Blueprint(
    "teacher_quizzes",
    __name__,
    url_prefix="/api/teacher-quizzes",
)

create_quiz_schema = CreateTeacherQuizSchema()

# Expand after corresponding verified RAG datasets are ready.
SUPPORTED_TOPIC_SLUGS = {"number-systems"}

SSC_PRACTICE_SLUGS = {
    f"ssc-ict-{slug}"
    for slug in (
        "ict-in-everyday-life",
        "e-learning",
        "e-governance-and-e-services",
        "e-commerce",
        "preventive-and-corrective-maintenance",
        "installing-and-uninstalling-software",
        "public-and-confidential-information",
        "cyber-risks-and-responsible-access",
        "internet-and-digital-content",
        "e-books-and-learning-resources",
        "word-processing",
        "save-and-save-as",
        "document-formatting-and-tables",
        "spreadsheets-and-cell-references",
        "multimedia-and-interactivity",
        "planning-a-presentation",
        "problem-solving-before-coding",
        "python-output-and-variables",
        "python-input-and-arithmetic",
        "python-decisions",
        "python-repetition-and-range",
        "bits-and-bytes-hsc-bridge",
        "binary-place-value-hsc-bridge",
        "first-html-page-optional-practice",
        "files-before-web-development",
    )
}
PAGE_SIZE = 20


def get_current_teacher() -> User:
    user = db.session.get(User, int(get_jwt_identity()))

    if user is None:
        abort(
            make_response(
                jsonify({"error": "User account no longer exists"}),
                404,
            )
        )

    if user.role != "teacher":
        abort(
            make_response(
                jsonify({
                    "error": "Only teachers can manage teacher quizzes"
                }),
                403,
            )
        )

    return user


def serialize_teacher_quiz(
    quiz: TeacherQuiz,
    *,
    include_questions: bool = False,
):
    data = {
        "id": quiz.id,
        "teacher_id": quiz.teacher_id,
        "topic_id": quiz.topic_id,
        "title": quiz.title,
        "response_language": quiz.response_language,
        "learning_mode": quiz.learning_mode,
        "status": quiz.status,
        "question_count": quiz.question_count,
        "created_at": quiz.created_at.isoformat(),
        "updated_at": quiz.updated_at.isoformat(),
        "published_at": (
            quiz.published_at.isoformat()
            if quiz.published_at is not None
            else None
        ),
    }

    if include_questions:
        # Only used after teacher ownership checks.
        data["questions"] = quiz.questions

    return data


def find_owned_quiz(
    teacher_id: int,
    quiz_id: str,
    *,
    lock: bool = False,
) -> TeacherQuiz | None:
    query = db.select(TeacherQuiz).where(
        TeacherQuiz.id == quiz_id,
        TeacherQuiz.teacher_id == teacher_id,
    )

    if lock:
        query = query.with_for_update()

    return db.session.scalar(query)


@teacher_quizzes_bp.post("")
@jwt_required()
def create_teacher_quiz():
    teacher = get_current_teacher()
    request_data = request.get_json(silent=True)

    if not isinstance(request_data, dict):
        return jsonify({
            "error": "Request body must be a JSON object"
        }), 400

    try:
        data = cast(
            dict[str, int | str],
            create_quiz_schema.load(request_data),
        )
    except ValidationError as error:
        return jsonify({
            "error": "Validation failed",
            "messages": error.messages,
        }), 400

    topic_id = cast(int, data["topic_id"])
    title = cast(str, data["title"])
    response_language = cast(str, data["response_language"])
    question_count = cast(int, data["question_count"])
    learning_mode = cast(str, data["learning_mode"])

    topic = db.session.get(Topic, topic_id)

    if topic is None:
        return jsonify({"error": "Topic not found"}), 404

    is_supported_hsc_topic = (
        topic.subject == "ict"
        and topic.academic_level == "hsc"
        and topic.slug in SUPPORTED_TOPIC_SLUGS
    )

    is_supported_ssc_topic = (
        topic.subject == "ict"
        and topic.academic_level == "ssc"
        and topic.slug in SSC_PRACTICE_SLUGS
    )

    if not (is_supported_hsc_topic or is_supported_ssc_topic):
        return jsonify({
            "error": "AI quiz generation is not available for this topic yet"
        }), 400

    try:
        # Preserve the service's existing five-question default.
        if question_count == 5:
            questions = generate_quiz(
                topic_title=topic.title,
                response_language=response_language,
                learning_mode=learning_mode,
                subject=topic.subject,
                academic_level=topic.academic_level,
            )
        else:
            questions = generate_quiz(
                topic_title=topic.title,
                response_language=response_language,
                question_count=question_count,
                learning_mode=learning_mode,
                subject=topic.subject,
                academic_level=topic.academic_level,
            )

        # Validate generated content before saving the draft.
        validated = cast(
            dict[str, str | list[dict[str, str]]],
            UpdateTeacherQuizSchema(
                expected_question_count=question_count,
            ).load({
                "title": title,
                "questions": questions,
            }),
        )

    except QuizGenerationError as error:
        db.session.rollback()
        return jsonify({"error": str(error)}), error.status_code

    except ValidationError:
        db.session.rollback()
        return jsonify({
            "error": "Generated quiz is invalid. Please try again."
        }), 502

    quiz = TeacherQuiz(
        teacher_id=teacher.id,
        topic_id=topic.id,
        title=cast(str, validated["title"]),
        response_language=response_language,
        questions=cast(
            list[dict[str, str]],
            validated["questions"],
        ),
        question_count=question_count,
        learning_mode=learning_mode,
    )

    try:
        db.session.add(quiz)
        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Could not save quiz draft. Try again later."
        }), 500

    return jsonify({
        "message": "Quiz draft generated successfully",
        "quiz": serialize_teacher_quiz(
            quiz,
            include_questions=True,
        ),
    }), 201


@teacher_quizzes_bp.get("")
@jwt_required()
def list_teacher_quizzes():
    teacher = get_current_teacher()
    raw_page = request.args.get("page", "1")
    list_view = request.args.get("view", "active")

    if list_view not in {"active", "history"}:
        return jsonify({
            "error": "View must be active or history"
        }), 400

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

    query = db.select(TeacherQuiz).where(
        TeacherQuiz.teacher_id == teacher.id,
    )

    if list_view == "history":
        query = query.where(
            TeacherQuiz.removed_at.is_not(None),
        ).order_by(
            db.desc(TeacherQuiz.removed_at),
            db.desc(TeacherQuiz.id),
        )
    else:
        query = query.where(
            TeacherQuiz.removed_at.is_(None),
        ).order_by(
            db.desc(TeacherQuiz.created_at),
            db.desc(TeacherQuiz.id),
        )

    quizzes = db.session.scalars(
        query
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE + 1)
    ).all()

    return jsonify({
        "quizzes": [
            serialize_teacher_quiz(quiz)
            for quiz in quizzes[:PAGE_SIZE]
        ],
        "pagination": {
            "page": page,
            "page_size": PAGE_SIZE,
            "has_more": len(quizzes) > PAGE_SIZE,
        },
    }), 200

@teacher_quizzes_bp.get("/<string:quiz_id>")
@jwt_required()
def get_teacher_quiz(quiz_id):
    teacher = get_current_teacher()
    quiz = find_owned_quiz(teacher.id, quiz_id)

    if quiz is None:
        return jsonify({
            "error": "Teacher quiz not found"
        }), 404

    return jsonify({
        "quiz": serialize_teacher_quiz(
            quiz,
            include_questions=True,
        ),
    }), 200


@teacher_quizzes_bp.put("/<string:quiz_id>")
@jwt_required()
def update_teacher_quiz(quiz_id):
    teacher = get_current_teacher()
    request_data = request.get_json(silent=True)

    if not isinstance(request_data, dict):
        return jsonify({
            "error": "Request body must be a JSON object"
        }), 400

    try:
        # Lock before reading the saved count or changing the draft.
        quiz = find_owned_quiz(
            teacher.id,
            quiz_id,
            lock=True,
        )

        if quiz is None:
            db.session.rollback()
            return jsonify({
                "error": "Teacher quiz not found"
            }), 404

        if quiz.status != "draft":
            db.session.rollback()
            return jsonify({
                "error": "Published quizzes cannot be edited."
            }), 409

        try:
            data = cast(
                dict[str, str | list[dict[str, str]]],
                UpdateTeacherQuizSchema(
                    expected_question_count=quiz.question_count,
                ).load(request_data),
            )
        except ValidationError as error:
            db.session.rollback()
            return jsonify({
                "error": "Validation failed",
                "messages": error.messages,
            }), 400

        questions = cast(
            list[dict[str, str]],
            data["questions"],
        )

        quiz.title = cast(str, data["title"])

        # Replace the full JSON list so SQLAlchemy tracks changes.
        quiz.questions = sorted(
            questions,
            key=lambda question: int(question["id"]),
        )

        quiz.updated_at = datetime.now(timezone.utc)
        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Could not update quiz draft. Try again later."
        }), 500

    return jsonify({
        "message": "Quiz draft updated successfully",
        "quiz": serialize_teacher_quiz(
            quiz,
            include_questions=True,
        ),
    }), 200


@teacher_quizzes_bp.post("/<string:quiz_id>/publish")
@jwt_required()
def publish_teacher_quiz(quiz_id):
    teacher = get_current_teacher()
    request_data = request.get_json(silent=True)

    if not isinstance(request_data, dict) or request_data:
        return jsonify({
            "error": "Request body must be an empty JSON object"
        }), 400

    try:
        quiz = find_owned_quiz(
            teacher.id,
            quiz_id,
            lock=True,
        )

        if quiz is None:
            db.session.rollback()
            return jsonify({
                "error": "Teacher quiz not found"
            }), 404

        if quiz.status != "draft":
            db.session.rollback()
            return jsonify({
                "error": "This quiz has already been published."
            }), 409

        try:
            validated = cast(
                dict[str, str | list[dict[str, str]]],
                UpdateTeacherQuizSchema(
                    expected_question_count=quiz.question_count,
                ).load({
                    "title": quiz.title,
                    "questions": quiz.questions,
                }),
            )
        except ValidationError as error:
            db.session.rollback()
            return jsonify({
                "error": "Quiz draft is invalid. Review it before publishing.",
                "messages": error.messages,
            }), 400

        questions = cast(
            list[dict[str, str]],
            validated["questions"],
        )

        quiz.title = cast(str, validated["title"])
        quiz.questions = sorted(
            questions,
            key=lambda question: int(question["id"]),
        )

        now = datetime.now(timezone.utc)
        quiz.status = "published"
        quiz.published_at = now
        quiz.updated_at = now

        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Could not publish quiz. Try again later."
        }), 500

    return jsonify({
        "message": "Quiz published successfully",
        "quiz": serialize_teacher_quiz(
            quiz,
            include_questions=True,
        ),
    }), 200

@teacher_quizzes_bp.patch("/<string:quiz_id>/remove")
@jwt_required()
def remove_teacher_quiz(quiz_id):
    teacher = get_current_teacher()
    request_data = request.get_json(silent=True)

    if not isinstance(request_data, dict) or request_data:
        return jsonify({
            "error": "Request body must be an empty JSON object"
        }), 400

    try:
        quiz = find_owned_quiz(
            teacher.id,
            quiz_id,
            lock=True,
        )

        if quiz is None:
            db.session.rollback()
            return jsonify({
                "error": "Teacher quiz not found"
            }), 404

        # Repeated requests preserve the original removal time.
        if quiz.removed_at is None:
            quiz.removed_at = datetime.now(timezone.utc)

        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Could not move quiz to history. Try again later."
        }), 500

    return jsonify({
        "message": "Quiz moved to history",
        "quiz_id": quiz_id,
    }), 200