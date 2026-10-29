from flask import Blueprint, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required

from extensions import db
from models.quiz_attempt import QuizAttempt
from models.topic import Topic
from models.user import User
from services.mastery_service import get_mastery_status


progress_bp = Blueprint(
    "progress",
    __name__,
    url_prefix="/api/progress",
)


@progress_bp.get("")
@jwt_required()
def get_learning_progress():
    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)

    if user is None:
        return jsonify({
            "error": "User account no longer exists",
        }), 404

    if user.role != "student":
        return jsonify({
            "error": "Only students can view learning progress",
        }), 403

    if user.academic_level not in ("ssc", "hsc"):
        return jsonify({
            "error": "Choose your study level before viewing progress",
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

    topic_progress_list = []

    for topic in topics:
        topic_attempts = attempts_by_topic.get(topic.id, [])
        latest_attempt = (
            topic_attempts[0]
            if topic_attempts
            else None
        )

        percentage = (
            round(
                latest_attempt.score
                / latest_attempt.total_questions
                * 100
            )
            if latest_attempt is not None
            else None
        )

        topic_progress_list.append({
            "topic_id": topic.id,
            "title": topic.title,
            "slug": topic.slug,
            "attempt_count": len(topic_attempts),
            "latest_score": (
                latest_attempt.score
                if latest_attempt is not None
                else None
            ),
            "total_questions": (
                latest_attempt.total_questions
                if latest_attempt is not None
                else None
            ),
            "percentage": percentage,
            "mastery_status": get_mastery_status(topic_attempts),
        })

    completed_topics = sum(
        item["attempt_count"] > 0
        for item in topic_progress_list
    )

    return jsonify({
        "summary": {
            "completed_topics": completed_topics,
            "total_topics": len(topics),
        },
        "topics": topic_progress_list,
    }), 200


@progress_bp.get("/weak-topics")
@jwt_required()
def get_weak_topics():
    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)

    if user is None:
        return jsonify({
            "error": "User account no longer exists",
        }), 404

    if user.role != "student":
        return jsonify({
            "error": "Only students can view weak topics",
        }), 403

    if user.academic_level not in ("ssc", "hsc"):
        return jsonify({
            "error": "Choose your study level before viewing progress",
            "code": "ACADEMIC_LEVEL_REQUIRED",
        }), 409

    topics = db.session.scalars(
        db.select(Topic)
        .where(
            Topic.academic_level == user.academic_level,
            Topic.subject == "ict",
        )
        .order_by(Topic.display_order, Topic.id)
    ).all()

    attempts = db.session.scalars(
        db.select(QuizAttempt)
        .join(Topic, Topic.id == QuizAttempt.topic_id)
        .where(
            QuizAttempt.user_id == user_id,
            Topic.academic_level == user.academic_level,
            Topic.subject == "ict",
        )
        .order_by(
            QuizAttempt.completed_at.desc(),
            QuizAttempt.id.desc(),
        )
    ).all()

    attempts_by_topic = {}

    for attempt in attempts:
        attempts_by_topic.setdefault(
            attempt.topic_id, []
        ).append(attempt)

    weak_topics = []
    other_practised_topics = []
    not_practised_topics = []

    for topic in topics:
        topic_attempts = attempts_by_topic.get(topic.id, [])

        if not topic_attempts:
            not_practised_topics.append({
                "topic_id": topic.id,
                "title": topic.title,
                "slug": topic.slug,
                "attempt_count": 0,
                "mastery_status": "not_started",
            })
            continue

        latest = topic_attempts[0]
        previous = (
            topic_attempts[1]
            if len(topic_attempts) > 1
            else None
        )

        latest_percentage = (
            latest.score / latest.total_questions * 100
        )

        previous_percentage = (
            previous.score / previous.total_questions * 100
            if previous is not None
            else None
        )

        trend = "not_enough_attempts"

        if previous is not None:
            comparison = (
                latest.score * previous.total_questions
                - previous.score * latest.total_questions
            )

            trend = (
                "improving"
                if comparison > 0
                else "declining"
                if comparison < 0
                else "unchanged"
            )

        item = {
            "topic_id": topic.id,
            "title": topic.title,
            "slug": topic.slug,
            "attempt_count": len(topic_attempts),
            "latest_score": latest.score,
            "total_questions": latest.total_questions,
            "latest_percentage": round(latest_percentage, 1),
            "previous_percentage": (
                round(previous_percentage, 1)
                if previous_percentage is not None
                else None
            ),
            "trend": trend,
            "mastery_status": get_mastery_status(topic_attempts),
        }

        if latest.score * 100 < latest.total_questions * 80:
            weak_topics.append(item)
        else:
            other_practised_topics.append(item)

    # Compare actual ratios, rather than rounded percentages.
    weak_topics.sort(
        key=lambda item: (
            item["latest_score"] / item["total_questions"],
            item["topic_id"],
        )
    )

    return jsonify({
        "basis": "latest_completed_attempt_per_topic",
        "practice_threshold_percentage": 80,
        "summary": {
            "total_topics": len(topics),
            "weak_topics": len(weak_topics),
            "other_practised_topics": len(other_practised_topics),
            "not_practised_topics": len(not_practised_topics),
        },
        "weak_topics": weak_topics,
        "other_practised_topics": other_practised_topics,
        "not_practised_topics": not_practised_topics,
    }), 200