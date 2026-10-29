from flask import Blueprint, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required

from extensions import db
from models.quiz_attempt import QuizAttempt
from models.topic import Topic
from models.user import User
from services.mastery_service import (
    MASTERY_PRIORITY,
    get_mastery_status,
)


recommendations_bp = Blueprint(
    "recommendations",
    __name__,
    url_prefix="/api/recommendations",
)


@recommendations_bp.get("/next-topic")
@jwt_required()
def get_next_topic_recommendation():
    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)

    if user is None:
        return jsonify({
            "error": "User account no longer exists",
        }), 404

    if user.role != "student":
        return jsonify({
            "error": "Only students can view learning recommendations",
        }), 403

    if user.academic_level not in ("ssc", "hsc"):
        return jsonify({
            "error": "Choose your study level before viewing recommendations",
            "code": "ACADEMIC_LEVEL_REQUIRED",
        }), 409

    topics = db.session.scalars(
        db.select(Topic)
        .where(Topic.academic_level == user.academic_level)
        .order_by(
            Topic.display_order,
            Topic.id,
        )
    ).all()

    if not topics:
        return jsonify({
            "error": "No learning topics found",
        }), 404

    attempts = db.session.scalars(
        db.select(QuizAttempt)
        .join(Topic, Topic.id == QuizAttempt.topic_id)
        .where(
            QuizAttempt.user_id == user_id,
            Topic.academic_level == user.academic_level,
        )
        .order_by(
            QuizAttempt.completed_at.desc(),
            QuizAttempt.id.desc(),
        )
    ).all()

    attempts_by_topic: dict[int, list[QuizAttempt]] = {}

    for attempt in attempts:
        attempts_by_topic.setdefault(
            attempt.topic_id,
            [],
        ).append(attempt)

    for topic in topics:
        if not attempts_by_topic.get(topic.id):
            return jsonify({
                "recommendation": {
                    "topic": topic.title,
                    "slug": topic.slug,
                    "mastery_status": "not_started",
                    "reason": (
                        "Ei topic ekhono quiz diye practice koro nai."
                    ),
                },
            }), 200

    def recommendation_priority(topic: Topic):
        topic_attempts = attempts_by_topic[topic.id]
        latest = topic_attempts[0]
        status = get_mastery_status(topic_attempts)

        return (
            MASTERY_PRIORITY[status],
            latest.score / latest.total_questions,
            topic.display_order,
            topic.id,
        )

    recommended_topic = min(
        topics,
        key=recommendation_priority,
    )

    topic_attempts = attempts_by_topic[recommended_topic.id]
    latest = topic_attempts[0]
    mastery_status = get_mastery_status(topic_attempts)

    percentage = round(
        latest.score / latest.total_questions * 100
    )

    if mastery_status == "almost_mastered":
        reason = (
            f"Tomar latest quiz score {percentage}% chilo. "
            "Arekbar 80% ba tar beshi score kore "
            "ei topic-er practice confirm koro."
        )
    elif mastery_status == "mastered":
        reason = (
            "Shob topic-e latest duita attempt-e 80% ba beshi "
            "score korecho. Ei topic revise kore practice dhore rakho."
        )
    else:
        reason = (
            f"Tomar latest quiz score {percentage}% chilo. "
            "Ei topic arekbar practice koro."
        )

    return jsonify({
        "recommendation": {
            "topic": recommended_topic.title,
            "slug": recommended_topic.slug,
            "mastery_status": mastery_status,
            "reason": reason,
        },
    }), 200