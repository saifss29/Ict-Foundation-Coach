from typing import cast

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from marshmallow import ValidationError

from extensions import db
from models.quiz_attempt import QuizAttempt
from models.quiz_question import QuizQuestion
from models.topic import Topic
from schemas.quiz_schema import QuizSubmissionSchema
from models.user import User


quizzes_bp = Blueprint("quizzes", __name__, url_prefix="/api/topics")

quiz_submission_schema = QuizSubmissionSchema()
def check_student_topic_access(topic):
    user = db.session.get(User, int(get_jwt_identity()))

    if user is None:
        return None, (
            jsonify({"error": "User account no longer exists"}),
            404,
        )

    if user.role != "student":
        return None, (
            jsonify({"error": "Only students can access practice quizzes"}),
            403,
        )

    if user.academic_level not in ("ssc", "hsc"):
        return None, (
            jsonify({
                "error": "Select SSC or HSC to access practice quizzes.",
                "code": "ACADEMIC_LEVEL_REQUIRED",
            }),
            409,
        )

    if topic.academic_level != user.academic_level:
        return None, (
            jsonify({
                "error": "This topic is not available for your study level.",
                "code": "TOPIC_LEVEL_MISMATCH",
            }),
            403,
        )

    return user, None


@quizzes_bp.get("/<string:topic_slug>/quiz")
@jwt_required()
def get_topic_quiz(topic_slug):
    topic = db.session.scalar(
        db.select(Topic).where(Topic.slug == topic_slug)
    )

    if topic is None:
        return jsonify({
            "error": "Topic not found"
        }), 404

    user, access_error = check_student_topic_access(topic)

    if access_error is not None:
        return access_error

    if user is None:
        return jsonify({
            "error": "User account no longer exists"
        }), 404

    questions = db.session.scalars(
        db.select(QuizQuestion)
        .where(QuizQuestion.topic_id == topic.id)
        .order_by(QuizQuestion.display_order)
    ).all()

    return jsonify({
        "topic": {
            "id": topic.id,
            "title": topic.title,
            "slug": topic.slug,
        },
        "questions": [
            {
                "id": question.id,
                "question_text": question.question_text,
                "options": [
                    {"key": "A", "text": question.option_a},
                    {"key": "B", "text": question.option_b},
                    {"key": "C", "text": question.option_c},
                    {"key": "D", "text": question.option_d},
                ],
            }
            for question in questions
        ],
    }), 200


@quizzes_bp.post("/<string:topic_slug>/quiz/submit")
@jwt_required()
def submit_topic_quiz(topic_slug):
    request_data = request.get_json(silent=True)

    if request_data is None:
        return jsonify({
            "error": "Request body must be valid JSON"
        }), 400

    try:
        submission_data = cast(
            dict[str, list[dict[str, int | str]]],
            quiz_submission_schema.load(request_data),
        )
    except ValidationError as error:
        return jsonify({
            "error": "Validation failed",
            "messages": error.messages,
        }), 400

    topic = db.session.scalar(
        db.select(Topic).where(Topic.slug == topic_slug)
    )

    if topic is None:
        return jsonify({
            "error": "Topic not found"
        }), 404

    user, access_error = check_student_topic_access(topic)

    if access_error is not None:
        return access_error

    if user is None:
        return jsonify({
            "error": "User account no longer exists"
        }), 404

    questions = db.session.scalars(
        db.select(QuizQuestion)
        .where(QuizQuestion.topic_id == topic.id)
        .order_by(QuizQuestion.display_order)
    ).all()

    if not questions:
        return jsonify({
            "error": "No quiz questions found for this topic"
        }), 404

    answers = submission_data["answers"]

    submitted_answers = {
        int(answer["question_id"]): str(answer["selected_option"])
        for answer in answers
    }

    expected_question_ids = {
        question.id
        for question in questions
    }

    if (
        len(submitted_answers) != len(answers)
        or set(submitted_answers) != expected_question_ids
    ):
        return jsonify({
            "error": "Submit exactly one answer for every quiz question"
        }), 400

    score = 0
    results = []

    for question in questions:
        selected_option = submitted_answers[question.id]
        is_correct = selected_option == question.correct_option

        if is_correct:
            score += 1

        results.append({
            "question_id": question.id,
            "selected_option": selected_option,
            "correct_option": question.correct_option,
            "is_correct": is_correct,
            "explanation": question.explanation,
        })

    quiz_attempt = QuizAttempt(
        user_id=user.id,
        topic_id=topic.id,
        score=score,
        total_questions=len(questions),
    )

    db.session.add(quiz_attempt)
    db.session.commit()

    return jsonify({
        "message": "Quiz submitted successfully",
        "attempt": {
            "id": quiz_attempt.id,
            "topic": topic.title,
            "score": score,
            "total_questions": len(questions),
        },
        "results": results,
    }), 201