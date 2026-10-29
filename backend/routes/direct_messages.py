from datetime import datetime, timezone
from typing import cast
from flask import Blueprint, abort, jsonify, make_response, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from extensions import db
from models.direct_conversation import DirectConversation
from models.direct_message import DirectMessage
from models.notification import Notification
from models.user import User
from schemas.direct_message_schema import (
    CreateDirectConversationSchema,
    SendDirectMessageSchema,
)


direct_messages_bp = Blueprint(
    "direct_messages",
    __name__,
    url_prefix="/api/messages",
)

create_conversation_schema = CreateDirectConversationSchema()
send_message_schema = SendDirectMessageSchema()

PAGE_SIZE = 20


def get_current_user() -> User:
    user = db.session.get(User, int(get_jwt_identity()))

    if user is None:
        abort(
            make_response(
                jsonify({
                    "error": "User account no longer exists"
                }),
                404,
            )
        )

    return user

def check_user_access(user):
    if user is None:
        return jsonify({
            "error": "User account no longer exists"
        }), 404

    if user.role not in {"student", "teacher"}:
        return jsonify({
            "error": "Account role is not supported"
        }), 403

    return None


def get_page():
    raw_page = request.args.get("page", "1")

    try:
        page = int(raw_page)
    except ValueError:
        return None

    if page < 1 or page > 10000:
        return None

    return page


def invalid_page_response():
    return jsonify({
        "error": "Page must be between 1 and 10000"
    }), 400


def participant_condition(user):
    if user.role == "teacher":
        return DirectConversation.teacher_id == user.id

    return DirectConversation.student_id == user.id


def find_conversation(user, conversation_id, *, lock=False):
    query = db.select(DirectConversation).where(
        DirectConversation.id == conversation_id,
        participant_condition(user),
    )

    if lock:
        query = query.with_for_update()

    return db.session.scalar(query)


def count_unread_messages(conversation_id, user_id):
    messages_table = db.metadata.tables["direct_messages"]

    return db.session.scalar(
        db.select(db.func.count())
        .select_from(messages_table)
        .where(
            messages_table.c["conversation_id"] == conversation_id,
            messages_table.c["sender_id"] != user_id,
            messages_table.c["read_at"].is_(None),
        )
    ) or 0


def serialize_conversation(conversation, user):
    other_user_id = (
        conversation.student_id
        if user.id == conversation.teacher_id
        else conversation.teacher_id
    )

    other_user = db.session.get(User, other_user_id)

    return {
        "id": conversation.id,
        "teacher_id": conversation.teacher_id,
        "student_id": conversation.student_id,
        "other_user": {
            "id": other_user_id,
            "name": (
                other_user.name
                if other_user is not None
                else "Unavailable account"
            ),
            "role": (
                other_user.role
                if other_user is not None
                else None
            ),
        },
        "created_at": conversation.created_at.isoformat(),
        "updated_at": conversation.updated_at.isoformat(),
        "unread_count": count_unread_messages(
            conversation.id,
            user.id,
        ),
    }


def serialize_message(message, user_id):
    return {
        "id": message.id,
        "conversation_id": message.conversation_id,
        "sender_id": message.sender_id,
        "content": message.content,
        "created_at": message.created_at.isoformat(),
        "read_at": (
            message.read_at.isoformat()
            if message.read_at is not None
            else None
        ),
        "is_mine": message.sender_id == user_id,
    }


@direct_messages_bp.get("/teachers")
@jwt_required()
def list_teachers():
    user = get_current_user()
    access_error = check_user_access(user)

    if access_error is not None:
        return access_error

    if user.role != "student":
        return jsonify({
            "error": "Only students can browse the teacher directory"
        }), 403

    page = get_page()

    if page is None:
        return invalid_page_response()

    users_table = db.metadata.tables["users"]

    teachers = db.session.scalars(
        db.select(User)
        .where(
            User.role == "teacher",
            users_table.c["is_email_verified"].is_(True),
        )
        .order_by(User.name, User.id)
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE + 1)
    ).all()

    return jsonify({
        "teachers": [
            {
                "id": teacher.id,
                "name": teacher.name,
            }
            for teacher in teachers[:PAGE_SIZE]
        ],
        "pagination": {
            "page": page,
            "page_size": PAGE_SIZE,
            "has_more": len(teachers) > PAGE_SIZE,
        },
    }), 200


@direct_messages_bp.post("/conversations")
@jwt_required()
def create_conversation():
    user = get_current_user()
    access_error = check_user_access(user)

    if access_error is not None:
        return access_error

    request_data = request.get_json(silent=True)

    if not isinstance(request_data, dict):
        return jsonify({
            "error": "Request body must be a JSON object"
        }), 400

    try:
        data = cast(
            dict[str, int],
            create_conversation_schema.load(request_data),
        )
    except ValidationError as error:
        return jsonify({
            "error": "Validation failed",
            "messages": error.messages,
        }), 400

    recipient = db.session.get(User, data["recipient_id"])
    expected_role = "teacher" if user.role == "student" else "student"

    if (
        recipient is None
        or recipient.role != expected_role
        or not recipient.is_email_verified
    ):
        return jsonify({
            "error": "Recipient not found or unavailable"
        }), 404

    teacher_id = (
        user.id if user.role == "teacher" else recipient.id
    )
    student_id = (
        user.id if user.role == "student" else recipient.id
    )

    pair_conditions = (
        DirectConversation.teacher_id == teacher_id,
        DirectConversation.student_id == student_id,
    )

    conversation = db.session.scalar(
        db.select(DirectConversation).where(*pair_conditions)
    )

    if conversation is not None:
        return jsonify({
            "conversation": serialize_conversation(
                conversation,
                user,
            ),
        }), 200

    conversation = DirectConversation(
        teacher_id=teacher_id,
        student_id=student_id,
    )

    try:
        db.session.add(conversation)
        db.session.commit()

    except IntegrityError:
        db.session.rollback()

        # Another request may have created the same pair first.
        existing = db.session.scalar(
            db.select(DirectConversation).where(*pair_conditions)
        )

        if existing is not None:
            return jsonify({
                "conversation": serialize_conversation(
                    existing,
                    user,
                ),
            }), 200

        return jsonify({
            "error": "Could not create conversation. Try again later."
        }), 500

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Could not create conversation. Try again later."
        }), 500

    return jsonify({
        "conversation": serialize_conversation(conversation, user),
    }), 201


@direct_messages_bp.get("/conversations")
@jwt_required()
def list_conversations():
    user = get_current_user()
    access_error = check_user_access(user)

    if access_error is not None:
        return access_error

    page = get_page()

    if page is None:
        return invalid_page_response()

    conversations = db.session.scalars(
        db.select(DirectConversation)
        .where(participant_condition(user))
        .order_by(
            db.desc(DirectConversation.updated_at),
            db.desc(DirectConversation.id),
        )
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE + 1)
    ).all()

    return jsonify({
        "conversations": [
            serialize_conversation(conversation, user)
            for conversation in conversations[:PAGE_SIZE]
        ],
        "pagination": {
            "page": page,
            "page_size": PAGE_SIZE,
            "has_more": len(conversations) > PAGE_SIZE,
        },
    }), 200


@direct_messages_bp.get(
    "/conversations/<int:conversation_id>/messages"
)
@jwt_required()
def list_messages(conversation_id):
    user = get_current_user()
    access_error = check_user_access(user)

    if access_error is not None:
        return access_error

    conversation = find_conversation(user, conversation_id)

    if conversation is None:
        return jsonify({
            "error": "Conversation not found"
        }), 404

    raw_before_id = request.args.get("before_id")
    before_id = None

    if raw_before_id is not None:
        try:
            before_id = int(raw_before_id)
        except ValueError:
            return jsonify({
                "error": "Before ID must be a positive integer"
            }), 400

        if before_id < 1:
            return jsonify({
                "error": "Before ID must be a positive integer"
            }), 400

    query = db.select(DirectMessage).where(
        DirectMessage.conversation_id == conversation.id
    )

    if before_id is not None:
        query = query.where(DirectMessage.id < before_id)

    messages = db.session.scalars(
        query
        .order_by(db.desc(DirectMessage.id))
        .limit(PAGE_SIZE + 1)
    ).all()

    visible_messages = list(reversed(messages[:PAGE_SIZE]))

    return jsonify({
        "conversation": serialize_conversation(conversation, user),
        "messages": [
            serialize_message(message, user.id)
            for message in visible_messages
        ],
        "pagination": {
            "page_size": PAGE_SIZE,
            "has_more": len(messages) > PAGE_SIZE,
            "next_before_id": (
                visible_messages[0].id
                if visible_messages
                else None
            ),
        },
    }), 200


@direct_messages_bp.post(
    "/conversations/<int:conversation_id>/messages"
)
@jwt_required()
def send_message(conversation_id):
    user = get_current_user()
    access_error = check_user_access(user)

    if access_error is not None:
        return access_error

    request_data = request.get_json(silent=True)

    if not isinstance(request_data, dict):
        return jsonify({
            "error": "Request body must be a JSON object"
        }), 400

    request_data = request_data.copy()

    if isinstance(request_data.get("content"), str):
        request_data["content"] = request_data["content"].strip()

    try:
        data = cast(
            dict[str, str],
            send_message_schema.load(request_data),
        )
    except ValidationError as error:
        return jsonify({
            "error": "Validation failed",
            "messages": error.messages,
        }), 400

    try:
        # Serialize writes to this conversation.
        conversation = find_conversation(
            user,
            conversation_id,
            lock=True,
        )

        if conversation is None:
            db.session.rollback()
            return jsonify({
                "error": "Conversation not found"
            }), 404

        recipient_id = (
            conversation.student_id
            if user.id == conversation.teacher_id
            else conversation.teacher_id
        )

        recipient = db.session.get(User, recipient_id)
        expected_role = (
            "student" if user.role == "teacher" else "teacher"
        )

        if (
            recipient is None
            or recipient.role != expected_role
            or not recipient.is_email_verified
        ):
            db.session.rollback()
            return jsonify({
                "error": "Recipient not found or unavailable"
            }), 404

        message = DirectMessage(
            conversation_id=conversation.id,
            sender_id=user.id,
            content=data["content"],
        )

        db.session.add(message)
        db.session.flush()

        notification = Notification(
            user_id=recipient_id,
            notification_type="direct_message",
            title="New message",
            message=f"{user.name} sent you a message.",
            direct_message_id=message.id,
        )

        db.session.add(notification)

        conversation.updated_at = datetime.now(timezone.utc)

        # Message, notification, and inbox timestamp save together.
        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Could not send message. Try again later."
        }), 500

    return jsonify({
        "message": serialize_message(message, user.id),
    }), 201


@direct_messages_bp.patch(
    "/conversations/<int:conversation_id>/read"
)
@jwt_required()
def mark_conversation_read(conversation_id):
    user = get_current_user()
    access_error = check_user_access(user)

    if access_error is not None:
        return access_error

    request_data = request.get_json(silent=True)

    if (
        not isinstance(request_data, dict)
        or set(request_data) != {"last_message_id"}
        or type(request_data["last_message_id"]) is not int
        or request_data["last_message_id"] < 1
    ):
        return jsonify({
            "error": "Provide a positive integer last_message_id"
        }), 400

    last_message_id = request_data["last_message_id"]

    try:
        conversation = find_conversation(
            user,
            conversation_id,
            lock=True,
        )

        if conversation is None:
            db.session.rollback()
            return jsonify({
                "error": "Conversation not found"
            }), 404

        boundary_message = db.session.scalar(
            db.select(DirectMessage).where(
                DirectMessage.id == last_message_id,
                DirectMessage.conversation_id == conversation.id,
            )
        )

        if boundary_message is None:
            db.session.rollback()
            return jsonify({
                "error": "Message not found in this conversation"
            }), 404

        messages_table = db.metadata.tables["direct_messages"]
        notifications_table = db.metadata.tables["notifications"]

        incoming_conditions = (
            messages_table.c["conversation_id"] == conversation.id,
            messages_table.c["sender_id"] != user.id,
            messages_table.c["id"] <= last_message_id,
        )

        incoming_message_ids = (
            db.select(messages_table.c["id"])
            .where(*incoming_conditions)
        )

        now = datetime.now(timezone.utc)

        db.session.execute(
            db.update(messages_table)
            .where(
                *incoming_conditions,
                messages_table.c["read_at"].is_(None),
            )
            .values(read_at=now)
        )

        db.session.execute(
            db.update(notifications_table)
            .where(
                notifications_table.c["user_id"] == user.id,
                notifications_table.c["notification_type"]
                == "direct_message",
                notifications_table.c["direct_message_id"].in_(
                    incoming_message_ids
                ),
                notifications_table.c["read_at"].is_(None),
            )
            .values(read_at=now)
        )

        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Could not mark messages as read. Try again later."
        }), 500

    return jsonify({
        "message": "Conversation messages marked as read",
        "unread_count": count_unread_messages(
            conversation.id,
            user.id,
        ),
    }), 200