from datetime import datetime, timedelta, timezone
from typing import Any, cast

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from marshmallow import RAISE, Schema, ValidationError, fields, validate
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from extensions import db
from models.calendar_event import CalendarEvent
from models.user import User
from schemas.calendar_event_schema import (
    CreateCalendarEventSchema,
    UpdateCalendarEventSchema,
)
from models.classroom import Classroom
from models.quiz_assignment import QuizAssignment
from models.quiz_assignment_recipient import QuizAssignmentRecipient
from models.teacher_quiz import TeacherQuiz
from models.notification import Notification
from schemas.calendar_assistant_schema import CalendarAssistantRequestSchema
from services.calendar_assistant_service import (
    CalendarAssistantError,
    generate_calendar_proposal,
)
import json
from hashlib import sha256

from models.calendar_event_create_request import CalendarEventCreateRequest


calendar_events_bp = Blueprint(
    "calendar_events",
    __name__,
    url_prefix="/api/calendar-events",
)

create_event_schema = CreateCalendarEventSchema()
update_event_schema = UpdateCalendarEventSchema()
calendar_assistant_schema = CalendarAssistantRequestSchema()
DeleteEventSchema = Schema.from_dict({
    "version": fields.Integer(
        required=True,
        strict=True,
        validate=validate.Range(min=1),
    ),
})
delete_event_schema = DeleteEventSchema(unknown=RAISE)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def serialize_event(event: CalendarEvent):
    return {
        "id": event.id,
        "title": event.title,
        "description": event.description,
        "starts_at": as_utc(event.starts_at).isoformat(),
        "ends_at": as_utc(event.ends_at).isoformat(),
        "timezone_name": event.timezone_name,
        "version": event.version,
        "created_at": as_utc(event.created_at).isoformat(),
        "updated_at": as_utc(event.updated_at).isoformat(),
    }


def current_calendar_user():
    user = db.session.get(User, int(get_jwt_identity()))

    if user is None:
        return None, (
            jsonify({"error": "User account no longer exists"}),
            404,
        )

    if user.role not in {"teacher", "student"}:
        return None, (
            jsonify({"error": "Only teachers and students can use the calendar"}),
            403,
        )

    return user, None


def load_event_body(schema: Schema):
    body = request.get_json(silent=True)

    if not isinstance(body, dict):
        return None, (
            jsonify({"error": "Request body must be a JSON object"}),
            400,
        )

    try:
        data = cast(dict[str, Any], schema.load(body))
    except ValidationError as error:
        return None, (
            jsonify({
                "error": "Validation failed",
                "messages": error.messages,
            }),
            400,
        )

    return data, None


def database_error():
    db.session.rollback()

    return jsonify({
        "error": "Could not complete calendar request. Try again later."
    }), 500

def replay_calendar_create(
    saved_request: CalendarEventCreateRequest,
    request_hash: str,
):
    if saved_request.request_hash != request_hash:
        return jsonify({
            "error": (
                "This request ID was already used with different event details. "
                "Use a new request ID for a new event."
            )
        }), 409

    return jsonify(saved_request.response_data), 201
@calendar_events_bp.post("")
@jwt_required()
def create_calendar_event():
    try:
        user, access_error = current_calendar_user()

        if access_error is not None:
            return access_error

        assert user is not None
        user_id = user.id

        data, validation_error = load_event_body(create_event_schema)

        if validation_error is not None:
            return validation_error

        assert data is not None

        raw_request_id = data.get("request_id")
        request_id = (
            str(raw_request_id)
            if raw_request_id is not None
            else None
        )

        normalized_event = {
            "title": data["title"],
            "description": data["description"],
            "starts_at": as_utc(data["starts_at"]).isoformat(),
            "ends_at": as_utc(data["ends_at"]).isoformat(),
            "timezone_name": data["timezone_name"],
        }

        request_hash = sha256(
            json.dumps(
                normalized_event,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()

        if request_id is not None:
            saved_request = db.session.get(
                CalendarEventCreateRequest,
                (user_id, request_id),
            )

            if saved_request is not None:
                return replay_calendar_create(
                    saved_request,
                    request_hash,
                )

        event = CalendarEvent(
            user_id=user_id,
            title=data["title"],
            description=data["description"],
            starts_at=data["starts_at"],
            ends_at=data["ends_at"],
            timezone_name=data["timezone_name"],
        )

        db.session.add(event)
        db.session.flush()

        db.session.add(
            Notification(
                user_id=user_id,
                notification_type="calendar_event_created",
                title="Calendar event created",
                message=f'You added "{event.title}" to your calendar.',
            )
        )

        response_body = {
            "message": "Calendar event created",
            "event": serialize_event(event),
        }

        if request_id is not None:
            db.session.add(
                CalendarEventCreateRequest(
                    user_id=user_id,
                    request_id=request_id,
                    request_hash=request_hash,
                    response_data=response_body,
                )
            )

        try:
            # Save the event, notification and request record together.
            db.session.commit()

        except IntegrityError:
            db.session.rollback()

            # Concurrent requests may both reach the insert.
            # The primary key allows only one to commit.
            if request_id is not None:
                saved_request = db.session.get(
                    CalendarEventCreateRequest,
                    (user_id, request_id),
                )

                if saved_request is not None:
                    return replay_calendar_create(
                        saved_request,
                        request_hash,
                    )

            return database_error()

        return jsonify(response_body), 201

    except SQLAlchemyError:
        return database_error()


@calendar_events_bp.get("")
@jwt_required()
def list_calendar_events():
    try:
        user, access_error = current_calendar_user()

        if access_error is not None:
            return access_error

        assert user is not None

        # Calendar requests supply the visible range with timezone offsets.
        try:
            range_start = datetime.fromisoformat(
                request.args.get("starts_at", "")
            )
            range_end = datetime.fromisoformat(
                request.args.get("ends_at", "")
            )

            if (
                range_start.utcoffset() is None
                or range_end.utcoffset() is None
            ):
                raise ValueError

            range_start = as_utc(range_start)
            range_end = as_utc(range_end)

            if (
                range_end <= range_start
                or range_end - range_start > timedelta(days=93)
            ):
                raise ValueError

        except ValueError:
            return jsonify({
                "error": (
                    "Provide timezone-aware starts_at and ends_at. "
                    "The range must be positive and no longer than 93 days."
                )
            }), 400

        try:
            page = int(request.args.get("page", "1"))

            if page < 1 or page > 10000:
                raise ValueError

        except ValueError:
            return jsonify({
                "error": "Page must be between 1 and 10000"
            }), 400

        page_size = 100
        events_table = db.metadata.tables["calendar_events"]

        # Include events overlapping the range, even if they started earlier.
        events = db.session.scalars(
            db.select(CalendarEvent)
            .where(
                CalendarEvent.user_id == user.id,
                events_table.c["starts_at"] < range_end,
                events_table.c["ends_at"] > range_start,
            )
            .order_by(
                events_table.c["starts_at"],
                events_table.c["id"],
            )
            .offset((page - 1) * page_size)
            .limit(page_size + 1)
        ).all()

        return jsonify({
            "events": [
                serialize_event(event)
                for event in events[:page_size]
            ],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "has_more": len(events) > page_size,
            },
        }), 200

    except SQLAlchemyError:
        return database_error()


@calendar_events_bp.get("/<string:event_id>")
@jwt_required()
def get_calendar_event(event_id):
    try:
        user, access_error = current_calendar_user()

        if access_error is not None:
            return access_error

        assert user is not None

        event = db.session.scalar(
            db.select(CalendarEvent).where(
                CalendarEvent.id == event_id,
                CalendarEvent.user_id == user.id,
            )
        )

        if event is None:
            return jsonify({"error": "Calendar event not found"}), 404

        return jsonify({"event": serialize_event(event)}), 200

    except SQLAlchemyError:
        return database_error()


@calendar_events_bp.put("/<string:event_id>")
@jwt_required()
def update_calendar_event(event_id):
    try:
        user, access_error = current_calendar_user()

        if access_error is not None:
            return access_error

        assert user is not None

        data, validation_error = load_event_body(update_event_schema)

        if validation_error is not None:
            return validation_error

        assert data is not None

        event = db.session.scalar(
            db.select(CalendarEvent)
            .where(
                CalendarEvent.id == event_id,
                CalendarEvent.user_id == user.id,
            )
            .with_for_update(of=CalendarEvent)
        )

        if event is None:
            db.session.rollback()
            return jsonify({"error": "Calendar event not found"}), 404

        if event.version != data["version"]:
            db.session.rollback()
            return jsonify({
                "error": "This event changed. Reload it before updating."
            }), 409

        
        if as_utc(event.starts_at) != as_utc(data["starts_at"]):
            event.reminder_sent_at = None

        event.title = data["title"]
        event.description = data["description"]
        event.starts_at = data["starts_at"]
        event.ends_at = data["ends_at"]
        event.timezone_name = data["timezone_name"]
        event.version += 1
        event.updated_at = datetime.now(timezone.utc)

        db.session.flush()

        db.session.add(
            Notification(
                user_id=user.id,
                notification_type="calendar_event_updated",
                title="Calendar event updated",
                message=f'You updated "{event.title}" in your calendar.',
            )
        )

        response_data = serialize_event(event)
        db.session.commit()

        return jsonify({
            "message": "Calendar event updated",
            "event": response_data,
        }), 200

    except SQLAlchemyError:
        return database_error()


@calendar_events_bp.delete("/<string:event_id>")
@jwt_required()
def delete_calendar_event(event_id):
    try:
        user, access_error = current_calendar_user()

        if access_error is not None:
            return access_error

        assert user is not None

        data, validation_error = load_event_body(delete_event_schema)

        if validation_error is not None:
            return validation_error

        assert data is not None

        event = db.session.scalar(
            db.select(CalendarEvent)
            .where(
                CalendarEvent.id == event_id,
                CalendarEvent.user_id == user.id,
            )
            .with_for_update(of=CalendarEvent)
        )

        if event is None:
            db.session.rollback()
            return jsonify({"error": "Calendar event not found"}), 404

        if event.version != data["version"]:
            db.session.rollback()
            return jsonify({
                "error": "This event changed. Reload it before deleting."
            }), 409

        db.session.delete(event)
        db.session.commit()

        return jsonify({
            "message": "Calendar event deleted",
        }), 200

    except SQLAlchemyError:
        return database_error()


@calendar_events_bp.get("/assignments")
@jwt_required()
def list_calendar_assignments():
    try:
        user, access_error = current_calendar_user()

        if access_error is not None:
            return access_error

        assert user is not None

        try:
            range_start = datetime.fromisoformat(
                request.args.get("starts_at", "")
            )
            range_end = datetime.fromisoformat(
                request.args.get("ends_at", "")
            )

            if (
                range_start.utcoffset() is None
                or range_end.utcoffset() is None
            ):
                raise ValueError

            range_start = as_utc(range_start)
            range_end = as_utc(range_end)

            if (
                range_end <= range_start
                or range_end - range_start > timedelta(days=93)
            ):
                raise ValueError

        except ValueError:
            return jsonify({
                "error": (
                    "Provide timezone-aware starts_at and ends_at. "
                    "The range must be positive and no longer than 93 days."
                )
            }), 400

        try:
            page = int(request.args.get("page", "1"))

            if page < 1 or page > 10000:
                raise ValueError

        except ValueError:
            return jsonify({
                "error": "Page must be between 1 and 10000"
            }), 400

        page_size = 100

        assignments_table = db.metadata.tables["quiz_assignments"]
        recipients_table = db.metadata.tables[
            "quiz_assignment_recipients"
        ]
        quizzes_table = db.metadata.tables["teacher_quizzes"]
        classrooms_table = db.metadata.tables["classrooms"]

        query = (
            db.select(
                QuizAssignment,
                quizzes_table.c["title"].label("quiz_title"),
                quizzes_table.c["question_count"],
                classrooms_table.c["name"].label("classroom_name"),
            )
            .join(
                TeacherQuiz,
                TeacherQuiz.id == QuizAssignment.quiz_id,
            )
            .join(
                Classroom,
                Classroom.id == QuizAssignment.classroom_id,
            )
            .where(
                # Availability window overlaps the visible calendar range.
                assignments_table.c["available_at"] < range_end,
                assignments_table.c["deadline_at"] > range_start,
            )
        )

        if user.role == "teacher":
            query = query.where(
                TeacherQuiz.teacher_id == user.id,
                Classroom.teacher_id == user.id,
            )
        else:
            is_recipient = (
                db.select(recipients_table.c["id"])
                .where(
                    recipients_table.c["assignment_id"]
                    == assignments_table.c["id"],
                    recipients_table.c["student_id"] == user.id,
                )
                .correlate(assignments_table)
                .exists()
            )

            query = query.where(is_recipient)

        rows = db.session.execute(
            query
            .order_by(
                assignments_table.c["available_at"],
                assignments_table.c["id"],
            )
            .offset((page - 1) * page_size)
            .limit(page_size + 1)
        ).mappings().all()

        items = []

        for row in rows[:page_size]:
            assignment = row["QuizAssignment"]

            items.append({
                "id": assignment.id,
                "assignment_id": assignment.id,
                "kind": "quiz_assignment",
                "read_only": True,
                "title": row["quiz_title"],
                "classroom_name": row["classroom_name"],
                "question_count": row["question_count"],
                "starts_at": as_utc(
                    assignment.available_at
                ).isoformat(),
                "ends_at": as_utc(
                    assignment.deadline_at
                ).isoformat(),
                "review_at": as_utc(
                    assignment.review_at
                ).isoformat(),
                "time_limit_minutes": assignment.time_limit_minutes,
                "max_attempts": assignment.max_attempts,
            })

        return jsonify({
            "assignments": items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "has_more": len(rows) > page_size,
            },
        }), 200

    except SQLAlchemyError:
        return database_error()


@calendar_events_bp.post("/assistant")
@jwt_required()
def create_calendar_assistant_proposal():
    try:
        user, access_error = current_calendar_user()

        if access_error is not None:
            return access_error

        assert user is not None

        data, validation_error = load_event_body(
            calendar_assistant_schema
        )

        if validation_error is not None:
            return validation_error

        assert data is not None

        selected_event = None
        event_id = None
        event_version = None

        if data["action"] == "update":
            event_id = str(data["event_id"])

            event = db.session.scalar(
                db.select(CalendarEvent).where(
                    CalendarEvent.id == event_id,
                    CalendarEvent.user_id == user.id,
                )
            )

            if event is None:
                return jsonify({
                    "error": "Calendar event not found"
                }), 404

            if event.version != data["version"]:
                return jsonify({
                    "error": (
                        "This event changed. Reload it before "
                        "requesting an update."
                    )
                }), 409

            selected_event = serialize_event(event)
            event_version = event.version

        # Release the read transaction before waiting for Maira.
        # The eventual Save request checks the version again.
        db.session.rollback()

        proposal = generate_calendar_proposal(
            message=data["message"],
            timezone_name=data["timezone_name"],
            action=data["action"],
            selected_event=selected_event,
        )

        return jsonify({
            "action": data["action"],
            "event_id": event_id,
            "version": event_version,
            "proposal": proposal,
        }), 200

    except CalendarAssistantError as error:
        db.session.rollback()

        return jsonify({
            "error": str(error),
        }), error.status_code

    except SQLAlchemyError:
        return database_error()