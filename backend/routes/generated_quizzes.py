from datetime import datetime, timezone
from typing import cast

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from marshmallow import ValidationError

from extensions import db
from models.generated_quiz import GeneratedQuiz
from models.quiz_attempt import QuizAttempt
from models.topic import Topic
from models.user import User
from schemas.quiz_schema import QuizSubmissionSchema
from services.quiz_generator import QuizGenerationError, generate_quiz
from models.chat_conversation import ChatConversation
from models.chat_message import ChatMessage


generated_quizzes_bp = Blueprint(
    "generated_quizzes",
    __name__,
    url_prefix="/api/generated-quizzes",
)

submission_schema = QuizSubmissionSchema()

# Expand this only after each topic's RAG dataset is ready.
SUPPORTED_TOPIC_SLUGS = {"number-systems"}
# Subject entries will be added through the seed script later.
SUBJECT_TOPIC_SLUGS = {"ssc-ict", "hsc-ict"}
# These lessons exist in the trained SSC starter dataset.
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

def check_student_access():
    user = db.session.get(User, int(get_jwt_identity()))

    if user is None:
        return jsonify({
            "error": "User account no longer exists"
        }), 404

    if user.role != "student":
        return jsonify({
            "error": "Only students can use generated quizzes"
        }), 403

    if user.academic_level not in ("ssc", "hsc"):
        return jsonify({
            "error": "Select SSC or HSC to access generated quizzes.",
            "code": "ACADEMIC_LEVEL_REQUIRED",
        }), 409

    return None


def check_topic_level_access(topic):
    user = db.session.get(User, int(get_jwt_identity()))

    if user is None:
        return jsonify({
            "error": "User account no longer exists"
        }), 404

    if topic.academic_level != user.academic_level:
        return jsonify({
            "error": "This topic is not available for your study level.",
            "code": "TOPIC_LEVEL_MISMATCH",
        }), 403

    return None


def has_expired(quiz):
    expires_at = quiz.expires_at

    # SQLite tests can return a datetime without timezone information.
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    return datetime.now(timezone.utc) >= expires_at


def serialize_quiz(quiz, topic):
    # Explicitly select public fields. Never send correct answers here.
    return {
        "id": quiz.id,
        "topic": {
            "id": topic.id,
            "title": topic.title,
            "slug": topic.slug,
            "subject": topic.subject,
            "academic_level": topic.academic_level,
        },
        "response_language": quiz.response_language,
        "learning_mode": quiz.learning_mode,
        "practice_topic": quiz.practice_topic,
        "expires_at": quiz.expires_at.isoformat(),
        "questions": [
            {
                "id": int(question["id"]),
                "question_text": question["question_text"],
                "options": [
                    {"key": "A", "text": question["option_a"]},
                    {"key": "B", "text": question["option_b"]},
                    {"key": "C", "text": question["option_c"]},
                    {"key": "D", "text": question["option_d"]},
                ],
            }
            for question in quiz.questions
        ],
    }


@generated_quizzes_bp.post("")
@jwt_required()
def create_generated_quiz():
    access_error = check_student_access()

    if access_error is not None:
        return access_error

    request_data = request.get_json(silent=True)

    if not isinstance(request_data, dict):
        return jsonify({
            "error": "Request body must be a JSON object"
        }), 400

    allowed_fields = {
        "topic_slug",
        "response_language",
        "learning_mode",
        "conversation_id",
    }

    if set(request_data) - allowed_fields:
        return jsonify({
            "error": "Request contains unexpected fields"
        }), 400

    topic_slug = request_data.get("topic_slug")

    if not isinstance(topic_slug, str) or not topic_slug.strip():
        return jsonify({
            "error": "Topic slug is required"
        }), 400

    topic_slug = topic_slug.strip()

    user_id = int(get_jwt_identity())
    conversation = None
    discussion_context = None
    practice_topic = None

    if "conversation_id" in request_data:
        conversation_id = request_data["conversation_id"]

        if (
            not isinstance(conversation_id, str)
            or not conversation_id.strip()
            or len(conversation_id.strip()) > 36
        ):
            return jsonify({
                "error": "Invalid conversation ID"
            }), 400

        conversation = db.session.scalar(
            db.select(ChatConversation).where(
                ChatConversation.id == conversation_id.strip(),
                ChatConversation.user_id == user_id,
            )
        )

        if conversation is None:
            return jsonify({
                "error": "Conversation not found"
            }), 404

    response_language = request_data.get(
        "response_language",
        conversation.response_language
        if conversation is not None
        else "banglish",
    )

    learning_mode = request_data.get(
        "learning_mode",
        conversation.learning_mode
        if conversation is not None
        else "personal_growth",
    )

    if (
        not isinstance(learning_mode, str)
        or learning_mode not in {
            "exam_preparation",
            "personal_growth",
        }
    ):
        return jsonify({
            "error": (
                "Learning mode must be exam_preparation "
                "or personal_growth"
            )
        }), 400

    if (
        not isinstance(response_language, str)
        or response_language not in {"banglish", "english"}
    ):
        return jsonify({
            "error": "Response language must be banglish or english"
        }), 400

    topic = db.session.scalar(
        db.select(Topic).where(Topic.slug == topic_slug)
    )

    if topic is None:
        return jsonify({"error": "Topic not found"}), 404

    level_error = check_topic_level_access(topic)

    if level_error is not None:
        return level_error

    if conversation is not None:
        if (
            conversation.topic != topic.title
            or conversation.response_language != response_language
            or conversation.learning_mode != learning_mode
        ):
            return jsonify({
                "error": (
                    "Quiz topic, language and learning mode "
                    "must match the conversation"
                )
            }), 409

        # Keep existing supported topics, and allow the new ICT
        # subject entries only through a saved discussion.
        is_ict_subject = (
            topic.slug == f"{topic.academic_level}-ict"
            and topic.slug in SUBJECT_TOPIC_SLUGS
            and topic.subject == "ict"
        )

        if (
            topic.slug not in SUPPORTED_TOPIC_SLUGS
            and not is_ict_subject
        ):
            return jsonify({
                "error": (
                    "AI quiz generation is not available "
                    "for this topic yet"
                )
            }), 400

        recent_messages = db.session.scalars(
            db.select(ChatMessage)
            .where(
                ChatMessage.conversation_id == conversation.id
            )
            .order_by(ChatMessage.id.desc())
            .limit(6)
        ).all()

        recent_messages = list(reversed(recent_messages))

        student_messages = [
            item
            for item in recent_messages
            if item.role == "student" and item.content.strip()
        ]

        assistant_messages = [
            item
            for item in recent_messages
            if item.role == "assistant" and item.content.strip()
        ]

        if not student_messages or not assistant_messages:
            return jsonify({
                "error": (
                    "Ask the tutor a question and receive "
                    "a reply before generating a quiz"
                )
            }), 400

        discussion_context = "\n\n".join(
            f"{item.role}: {item.content.strip()[:1500]}"
            for item in recent_messages
        )

        # Store the latest question as a short practice label.
        # The generator uses the full recent discussion to resolve
        # follow-ups such as "explain this again".
        practice_topic = student_messages[-1].content.strip()[:150]

    else:
        is_supported_legacy_topic = (
            topic.slug in SUPPORTED_TOPIC_SLUGS
        )

        is_supported_ssc_lesson = (
            topic.slug in SSC_PRACTICE_SLUGS
            and topic.subject == "ict"
            and topic.academic_level == "ssc"
        )

        if not (
            is_supported_legacy_topic
            or is_supported_ssc_lesson
        ):
            return jsonify({
                "error": (
                    "AI quiz generation is not available "
                    "for this topic yet"
                ),
            }), 400

        # Selected lesson title comes from the database.
        # No conversation or chat history is used.
        practice_topic = topic.title
    generator_arguments = {
        "topic_title": practice_topic or topic.title,
        "response_language": response_language,
        "learning_mode": learning_mode,
        "subject": topic.subject,
        "academic_level": topic.academic_level,
    }


    try:
        if discussion_context is not None:
            questions = generate_quiz(
                **generator_arguments,
                discussion_context=discussion_context,
            )
        else:
            questions = generate_quiz(**generator_arguments)

    except QuizGenerationError as error:
        return jsonify({
            "error": str(error)
        }), error.status_code

    quiz = GeneratedQuiz(
        user_id=user_id,
        topic_id=topic.id,
        response_language=response_language,
        questions=questions,
        learning_mode=learning_mode,
        practice_topic=practice_topic,
    )

    db.session.add(quiz)
    db.session.commit()

    return jsonify({
        "message": "Quiz generated successfully",
        "quiz": serialize_quiz(quiz, topic),
    }), 201

@generated_quizzes_bp.get("/<string:quiz_id>")
@jwt_required()
def get_generated_quiz(quiz_id):
    access_error = check_student_access()

    if access_error is not None:
        return access_error

    quiz = db.session.scalar(
        db.select(GeneratedQuiz).where(
            GeneratedQuiz.id == quiz_id,
            GeneratedQuiz.user_id == int(get_jwt_identity()),
        )
    )

    if quiz is None:
        return jsonify({"error": "Generated quiz not found"}), 404

    if quiz.attempt_id is not None:
        return jsonify({
            "error": "This quiz has already been submitted"
        }), 409

    if has_expired(quiz):
        return jsonify({
            "error": "This quiz has expired. Generate a new quiz."
        }), 410

    topic = db.session.get(Topic, quiz.topic_id)

    if topic is None:
        return jsonify({"error": "Topic not found"}), 404

    level_error = check_topic_level_access(topic)

    if level_error is not None:
        return level_error

    return jsonify({
        "quiz": serialize_quiz(quiz, topic),
    }), 200


@generated_quizzes_bp.post("/<string:quiz_id>/submit")
@jwt_required()
def submit_generated_quiz(quiz_id):
    access_error = check_student_access()

    if access_error is not None:
        return access_error

    request_data = request.get_json(silent=True)

    if not isinstance(request_data, dict):
        return jsonify({
            "error": "Request body must be a JSON object"
        }), 400

    try:
        submission = cast(
            dict[str, list[dict[str, int | str]]],
            submission_schema.load(request_data),
        )
    except ValidationError as error:
        return jsonify({
            "error": "Validation failed",
            "messages": error.messages,
        }), 400

    # PostgreSQL locks this row until commit.
    # Concurrent submissions cannot both create an attempt.
    quiz = db.session.scalar(
        db.select(GeneratedQuiz)
        .where(
            GeneratedQuiz.id == quiz_id,
            GeneratedQuiz.user_id == int(get_jwt_identity()),
        )
        .with_for_update()
    )

    if quiz is None:
        return jsonify({"error": "Generated quiz not found"}), 404

    if quiz.attempt_id is not None:
        return jsonify({
            "error": "This quiz has already been submitted"
        }), 409

    if has_expired(quiz):
        return jsonify({
            "error": "This quiz has expired. Generate a new quiz."
        }), 410

    topic = db.session.get(Topic, quiz.topic_id)

    if topic is None:
        return jsonify({"error": "Topic not found"}), 404

    level_error = check_topic_level_access(topic)

    if level_error is not None:
        return level_error

    answers = submission["answers"]

    submitted_answers = {
        int(answer["question_id"]): str(answer["selected_option"])
        for answer in answers
    }

    expected_ids = {
        int(question["id"])
        for question in quiz.questions
    }

    if (
        len(submitted_answers) != len(answers)
        or set(submitted_answers) != expected_ids
    ):
        return jsonify({
            "error": "Submit exactly one answer for every quiz question"
        }), 400

    score = 0
    results = []

    for question in quiz.questions:
        question_id = int(question["id"])
        selected_option = submitted_answers[question_id]
        is_correct = selected_option == question["correct_option"]

        if is_correct:
            score += 1

        results.append({
            "question_id": question_id,
            "selected_option": selected_option,
            "correct_option": question["correct_option"],
            "is_correct": is_correct,
            "explanation": question["explanation"],
        })

    attempt = QuizAttempt(
        user_id=quiz.user_id,
        topic_id=quiz.topic_id,
        score=score,
        total_questions=len(quiz.questions),
    )

    db.session.add(attempt)

    # Get the attempt ID without committing a partial transaction.
    db.session.flush()

    quiz.attempt_id = attempt.id
    db.session.commit()

    return jsonify({
        "message": "Quiz submitted successfully",
        "attempt": {
            "id": attempt.id,
            "topic": topic.title,
            "score": score,
            "total_questions": len(quiz.questions),
        },
        "results": results,
    }), 201