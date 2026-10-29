from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from models.direct_conversation import DirectConversation
from models.direct_message import DirectMessage
from models.notification import Notification
from models.user import User


notifications_bp = Blueprint(
    "notifications",
    __name__,
    url_prefix="/api/notifications",
)


def get_current_user():
    return db.session.get(User, int(get_jwt_identity()))


def get_notification_conversation_id(
    notification: Notification,
) -> int | None:
    if (
        notification.notification_type != "direct_message"
        or notification.direct_message_id is None
    ):
        return None

    # Return a chat target only if the notification owner
    # is a participant in that conversation.
    return db.session.scalar(
        db.select(DirectConversation.id)
        .join(
            DirectMessage,
            DirectMessage.conversation_id == DirectConversation.id,
        )
        .where(
            DirectMessage.id == notification.direct_message_id,
            db.or_(
                DirectConversation.teacher_id == notification.user_id,
                DirectConversation.student_id == notification.user_id,
            ),
        )
    )


def serialize_notification(notification: Notification):
    return {
        "id": notification.id,
        "notification_type": notification.notification_type,
        "title": notification.title,
        "message": notification.message,
        "feedback_id": notification.feedback_id,
        "direct_message_id": notification.direct_message_id,
        "conversation_id": get_notification_conversation_id(notification),
        "created_at": notification.created_at.isoformat(),
        "read_at": (
            notification.read_at.isoformat()
            if notification.read_at is not None
            else None
        ),
        "is_read": notification.read_at is not None,
    }


def count_unread_notifications(user_id):
    notifications_table = db.metadata.tables["notifications"]

    return db.session.scalar(
        db.select(db.func.count())
        .select_from(notifications_table)
        .where(
            notifications_table.c["user_id"] == user_id,
            notifications_table.c["read_at"].is_(None),
        )
    ) or 0


@notifications_bp.get("")
@jwt_required()
def list_my_notifications():
    user = get_current_user()

    if user is None:
        return jsonify({
            "error": "User account no longer exists"
        }), 404

    raw_page = request.args.get("page", "1")

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

    page_size = 20

    notifications = db.session.scalars(
        db.select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(
            db.desc(Notification.created_at),
            db.desc(Notification.id),
        )
        .offset((page - 1) * page_size)
        .limit(page_size + 1)
    ).all()

    return jsonify({
        "notifications": [
            serialize_notification(notification)
            for notification in notifications[:page_size]
        ],
        "unread_count": count_unread_notifications(user.id),
        "pagination": {
            "page": page,
            "page_size": page_size,
            "has_more": len(notifications) > page_size,
        },
    }), 200


@notifications_bp.get("/unread-count")
@jwt_required()
def get_unread_count():
    user = get_current_user()

    if user is None:
        return jsonify({
            "error": "User account no longer exists"
        }), 404

    return jsonify({
        "unread_count": count_unread_notifications(user.id),
    }), 200


@notifications_bp.patch("/<int:notification_id>/read")
@jwt_required()
def mark_notification_read(notification_id):
    user = get_current_user()

    if user is None:
        return jsonify({
            "error": "User account no longer exists"
        }), 404

    try:
        notification = db.session.scalar(
            db.select(Notification)
            .where(
                Notification.id == notification_id,
                Notification.user_id == user.id,
            )
            .with_for_update()
        )

        if notification is None:
            db.session.rollback()
            return jsonify({
                "error": "Notification not found"
            }), 404

        # Preserve the original timestamp if already read.
        if notification.read_at is None:
            notification.read_at = datetime.now(timezone.utc)

        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Could not mark notification as read. Try again later."
        }), 500

    return jsonify({
        "message": "Notification marked as read",
        "notification": serialize_notification(notification),
        "unread_count": count_unread_notifications(user.id),
    }), 200