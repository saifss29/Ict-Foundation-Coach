from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from extensions import db
from models.topic import Topic
from models.user import User
from services.topic_cache_service import (
    build_topic_cache_key,
    cache_topics,
    get_cached_topics,
)


topics_bp = Blueprint(
    "topics",
    __name__,
    url_prefix="/api/topics",
)


def get_accessible_topics_query():
    user = db.session.get(User, int(get_jwt_identity()))

    if user is None:
        return None, (
            jsonify({
                "error": "User account no longer exists",
            }),
            404,
        )

    if user.role not in ("student", "teacher"):
        return None, (
            jsonify({
                "error": "Only students and teachers can access topics",
            }),
            403,
        )

    query = db.select(Topic)

    if user.role == "student":
        if user.academic_level not in ("ssc", "hsc"):
            return None, (
                jsonify({
                    "error": "Select SSC or HSC to access learning topics.",
                    "code": "ACADEMIC_LEVEL_REQUIRED",
                }),
                409,
            )

        query = query.where(
            Topic.academic_level == user.academic_level
        )

    return query, None

def topic_cache_scope():
    user = db.session.get(User, int(get_jwt_identity()))

    if user is None:
        return None

    if user.role == "teacher":
        return "teacher:all-levels"

    if (
        user.role == "student"
        and user.academic_level in ("ssc", "hsc")
    ):
        return f"student:{user.academic_level}"

    return None
def serialize_topic(topic):
    return {
        "id": topic.id,
        "title": topic.title,
        "slug": topic.slug,
        "description": topic.description,
        "display_order": topic.display_order,
        "subject": topic.subject,
        "academic_level": topic.academic_level,
    }


@topics_bp.get("")
@jwt_required()
def list_topics():
    query, error_response = get_accessible_topics_query()

    if error_response is not None:
        return error_response

    if query is None:
        return jsonify({
            "error": "Could not load learning topics",
        }), 500

    scope = topic_cache_scope()

    cache_key = (
        build_topic_cache_key(
            scope=scope,
            endpoint="list",
        )
        if scope is not None
        else None
    )

    cached = get_cached_topics(cache_key)

    if cached is not None:
        return jsonify(cached), 200

    topics = db.session.scalars(
        query.order_by(
            Topic.display_order,
            Topic.id,
        )
    ).all()

    payload = {
        "topics": [
            serialize_topic(topic)
            for topic in topics
        ],
    }

    cache_topics(cache_key, payload)

    return jsonify(payload), 200


@topics_bp.get("/search")
@jwt_required()
def search_topics():
    query, error_response = get_accessible_topics_query()

    if error_response is not None:
        return error_response

    if query is None:
        return jsonify({
            "error": "Could not load learning topics",
        }), 500

    search_text = request.args.get("q", "").strip()
    raw_page = request.args.get("page", "1")

    if len(search_text) > 100:
        return jsonify({
            "error": "Search must be 100 characters or less",
        }), 400

    try:
        page = int(raw_page)
    except (TypeError, ValueError):
        return jsonify({
            "error": "Page must be a positive integer",
        }), 400

    if not 1 <= page <= 10000:
        return jsonify({
            "error": "Page must be between 1 and 10000",
        }), 400
    scope = topic_cache_scope()

    cache_key = (
        build_topic_cache_key(
            scope=scope,
            endpoint="search",
            search_text=search_text,
            page=page,
        )
        if scope is not None
        else None
    )

    cached = get_cached_topics(cache_key)

    if cached is not None:
        return jsonify(cached), 200

    # The practice picker contains ICT lessons only.
    # Broad subject cards are not individual practice lessons.
    topic_columns = db.metadata.tables["topics"].c


    query = query.where(
        topic_columns["subject"] == "ict",
        topic_columns["slug"].notin_(("ssc-ict", "hsc-ict")),
    )

    if search_text:
        # Treat %, _ and backslash as literal search characters.
        escaped_text = (
            search_text
            .replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )

        query = query.where(
            topic_columns["title"].ilike(
                f"%{escaped_text}%",
                escape="\\",
            )
        )

    page_size = 20

    topics = db.session.scalars(
        query.order_by(
            Topic.display_order,
            Topic.id,
        )
        .offset((page - 1) * page_size)
        .limit(page_size + 1)
    ).all()

    payload = {
        "topics": [
            serialize_topic(topic)
            for topic in topics[:page_size]
        ],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "has_more": len(topics) > page_size,
        },
    }

    cache_topics(cache_key, payload)

    return jsonify(payload), 200