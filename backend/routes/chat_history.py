from datetime import timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from extensions import db
from models.chat_conversation import ChatConversation
from models.chat_message import ChatMessage
from models.user import User


chat_history_bp = Blueprint(
    "chat_history",
    __name__,
    url_prefix="/api/chat/conversations",
)


def get_current_student():
    user = db.session.get(User, int(get_jwt_identity()))

    if user is None:
        return None, (
            jsonify({"error": "User account no longer exists"}),
            404,
        )

    if user.role != "student":
        return None, (
            jsonify({"error": "Only students can access chat history"}),
            403,
        )

    return user, None


def utc_iso(value):
    # SQLite may return naive datetimes; stored timestamps use UTC.
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc).isoformat()


def serialize_conversation(conversation):
    return {
        "id": conversation.id,
        "title": conversation.title,
        "topic": conversation.topic,
        "response_language": conversation.response_language,
        "learning_mode": conversation.learning_mode,
        "created_at": utc_iso(conversation.created_at),
        "updated_at": utc_iso(conversation.updated_at),
    }

def get_page_number():
    raw_page = request.args.get("page", "1")

    try:
        page = int(raw_page)
    except (ValueError, TypeError):
        return None

    return page if page >= 1 else None


@chat_history_bp.get("")
@jwt_required()
def list_conversations():
    user, error_response = get_current_student()

    if error_response is not None:
        return error_response

    if user is None:
        return jsonify({"error": "User account no longer exists"}), 404

    page = get_page_number()

    if page is None:
        return jsonify({
            "error": "Page must be a positive integer"
        }), 400

    query = (
        db.select(ChatConversation)
        .where(ChatConversation.user_id == user.id)
        .order_by(
            ChatConversation.updated_at.desc(),
            ChatConversation.id.desc(),
        )
    )

    pagination = db.paginate(
        query,
        page=page,
        per_page=20,
        max_per_page=20,
        error_out=False,
    )

    return jsonify({
        "conversations": [
            serialize_conversation(conversation)
            for conversation in pagination.items
        ],
        "pagination": {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "has_next": pagination.has_next,
        },
    }), 200


@chat_history_bp.get("/<string:conversation_id>")
@jwt_required()
def get_conversation_messages(conversation_id):
    user, error_response = get_current_student()

    if error_response is not None:
        return error_response

    if user is None:
        return jsonify({"error": "User account no longer exists"}), 404

    conversation = db.session.scalar(
        db.select(ChatConversation).where(
            ChatConversation.id == conversation_id,
            ChatConversation.user_id == user.id,
        )
    )

    if conversation is None:
        return jsonify({
            "error": "Conversation not found"
        }), 404

    page = get_page_number()

    if page is None:
        return jsonify({
            "error": "Page must be a positive integer"
        }), 400

    query = (
        db.select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation.id)
        .order_by(ChatMessage.id.asc())
    )

    pagination = db.paginate(
        query,
        page=page,
        per_page=50,
        max_per_page=50,
        error_out=False,
    )

    return jsonify({
        "conversation": serialize_conversation(conversation),
        "messages": [
            {
                "id": message.id,
                "role": message.role,
                "text": message.content,
                "created_at": utc_iso(message.created_at),
            }
            for message in pagination.items
        ],
        "pagination": {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "has_next": pagination.has_next,
        },
    }), 200