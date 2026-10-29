import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from marshmallow import RAISE, Schema, ValidationError, fields
from sqlalchemy import select

from extensions import db, limiter
from services.email_service import EmailDeliveryError, send_email
from services.parent_report_token_service import (
    read_parent_unsubscribe_token,
    verification_fingerprint,
)


parent_reports_bp = Blueprint(
    "parent_reports",
    __name__,
    url_prefix="/api/parent-reports",
)


class ParentEmailSchema(Schema):
    class Meta:
        unknown = RAISE

    parent_email = fields.Email(required=True)


def token_digest(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def student_row(*, lock=False):
    users = db.metadata.tables["users"]
    query = select(users).where(
        users.c.id == int(get_jwt_identity())
    )

    if lock:
        query = query.with_for_update()

    return db.session.execute(query).mappings().one_or_none()


def student_error(student):
    if student is None:
        return jsonify({"error": "User account no longer exists."}), 404

    if student["role"] != "student":
        return jsonify({
            "error": "Only students can manage parent reports."
        }), 403

    return None


@parent_reports_bp.get("")
@jwt_required()
def get_parent_report_preferences():
    student = student_row()
    error = student_error(student)

    if error is not None:
        return error
    assert student is not None
    return jsonify({
        "parent_email": student["parent_email"],
        "verified": student["parent_email_verified_at"] is not None,
        "enabled": student["weekly_report_enabled"],
    }), 200


def send_parent_verification(student, email, *, requested_by_teacher=False):
    users = db.metadata.tables["users"]
    tokens = db.metadata.tables["parent_email_verification_tokens"]
    now = datetime.now(timezone.utc)
    raw_token = secrets.token_urlsafe(32)

    db.session.execute(
        users.update()
        .where(users.c.id == student["id"])
        .values(
            parent_email=email,
            parent_email_verified_at=None,
            weekly_report_enabled=False,
        )
    )

    db.session.execute(
        tokens.update()
        .where(
            tokens.c.student_id == student["id"],
            tokens.c.used_at.is_(None),
        )
        .values(used_at=now)
    )

    db.session.execute(
        tokens.insert().values(
            student_id=student["id"],
            parent_email=email,
            token_hash=token_digest(raw_token),
            created_at=now,
            expires_at=now + timedelta(hours=24),
        )
    )

    frontend_url = current_app.config["FRONTEND_URL"].rstrip("/")
    link = (
        f"{frontend_url}/parent-reports/verify?"
        f"{urlencode({'token': raw_token})}"
    )

    request_description = (
        f"A teacher requested a parent email correction for {student['name']}."
        if requested_by_teacher
        else f"{student['name']} requested parent progress reports."
    )

    try:
        send_email(
            recipient=email,
            subject="Confirm parent progress reports",
            body=(
                "ICT Foundation Coach\n\n"
                f"{request_description}\n\n"
                "If you are authorised to receive this student's progress, "
                "open the link and confirm your consent:\n\n"
                f"{link}\n\n"
                "Reports include quiz progress, topics to practise and "
                "assignment progress. Regular delivery is weekly. "
                "During testing, delivery may occur every 5 minutes.\n\n"
                "This link expires in 24 hours. "
                "Opening it alone does not enable reports.\n"
                "If you did not expect this request, ignore it."
            ),
        )
    except EmailDeliveryError:
        db.session.rollback()
        return jsonify({
            "error": "Could not send the parent verification email."
        }), 502

    db.session.commit()

    return jsonify({
        "message": (
            "Verification email sent. Reports remain off until confirmed."
        )
    }), 200
@parent_reports_bp.post("/request-verification")
@jwt_required()
@limiter.limit("5 per hour")
def request_parent_email_verification():
    body = request.get_json(silent=True)

    if not isinstance(body, dict):
        return jsonify({"error": "Request body must be an object."}), 400

    cleaned = body.copy()

    if isinstance(cleaned.get("parent_email"), str):
        cleaned["parent_email"] = cleaned["parent_email"].strip()

    try:
        data = ParentEmailSchema().load(cleaned)
    except ValidationError as error:
        return jsonify({
            "error": "Enter a valid parent email.",
            "details": error.messages,
        }), 400

    if not isinstance(data, dict):
        return jsonify({"error": "Invalid request body."}), 400

    email = data.get("parent_email")

    if not isinstance(email, str):
        return jsonify({"error": "Enter a valid parent email."}), 400

    if len(email) > 255:
        return jsonify({"error": "Parent email is too long."}), 400

    student = student_row(lock=True)
    error = student_error(student)

    if error is not None:
        db.session.rollback()
        return error
    assert student is not None
    if student["parent_email_verified_at"] is not None:
        db.session.rollback()
        return jsonify({
            "error": (
                "Parent email is already verified. "
                "Students cannot change it or disable reports."
            )
        }), 403

    return send_parent_verification(student, email)


@parent_reports_bp.post("/verify")
@limiter.limit("20 per hour")
def verify_parent_email():
    body = request.get_json(silent=True)

    if (
        not isinstance(body, dict)
        or set(body) != {"token", "consent"}
        or body.get("consent") is not True
    ):
        return jsonify({
            "error": "A verification token and explicit consent are required."
        }), 400

    raw_token = body["token"]

    if (
        not isinstance(raw_token, str)
        or not 20 <= len(raw_token) <= 200
    ):
        return jsonify({"error": "Invalid verification link."}), 400

    users = db.metadata.tables["users"]
    tokens = db.metadata.tables["parent_email_verification_tokens"]
    digest = token_digest(raw_token)

    candidate = db.session.execute(
        select(tokens.c.student_id)
        .where(tokens.c.token_hash == digest)
    ).scalar_one_or_none()

    if candidate is None:
        return jsonify({"error": "Invalid verification link."}), 400

    # Use the same lock order as preference changes: user, then token.
    student = db.session.execute(
        select(users)
        .where(users.c.id == candidate)
        .with_for_update()
    ).mappings().one_or_none()

    token = db.session.execute(
        select(tokens)
        .where(tokens.c.token_hash == digest)
        .with_for_update()
    ).mappings().one_or_none()

    now = datetime.now(timezone.utc)

    if token is not None:
        expiry = token["expires_at"]
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
    else:
        expiry = now

    if (
        student is None
        or student["role"] != "student"
        or token is None
        or token["used_at"] is not None
        or expiry <= now
        or student["parent_email"] != token["parent_email"]
    ):
        db.session.rollback()
        return jsonify({
            "error": "This verification link is invalid or expired."
        }), 400

    db.session.execute(
        users.update()
        .where(users.c.id == student["id"])
        .values(
            parent_email_verified_at=now,
            weekly_report_enabled=True,
        )
    )

    db.session.execute(
        tokens.update()
        .where(tokens.c.id == token["id"])
        .values(used_at=now)
    )

    db.session.commit()

    return jsonify({
        "message": "Parent email confirmed. Progress reports are enabled."
    }), 200


@parent_reports_bp.delete("")
@jwt_required()
def disable_parent_reports():
    student = student_row()
    error = student_error(student)

    if error is not None:
        return error

    return jsonify({
        "error": (
            "Students cannot disable parent reports. "
            "The parent must use the unsubscribe link."
        )
    }), 403

@parent_reports_bp.post("/unsubscribe")
@limiter.limit("20 per hour")
def unsubscribe_parent_reports():
    body = request.get_json(silent=True)

    if (
        not isinstance(body, dict)
        or set(body) != {"token", "confirm"}
        or body.get("confirm") is not True
    ):
        return jsonify({
            "error": "An unsubscribe token and confirmation are required."
        }), 400

    try:
        payload = read_parent_unsubscribe_token(body["token"])
    except ValueError:
        return jsonify({"error": "Invalid unsubscribe link."}), 400

    users = db.metadata.tables["users"]

    student = db.session.execute(
        select(users)
        .where(users.c.id == payload["student_id"])
        .with_for_update()
    ).mappings().one_or_none()

    if (
        student is None
        or student["role"] != "student"
        or student["parent_email"] is None
        or student["parent_email_verified_at"] is None
    ):
        db.session.rollback()
        return jsonify({"error": "Invalid unsubscribe link."}), 400

    expected = verification_fingerprint(
        student["parent_email"],
        student["parent_email_verified_at"],
    )

    if not secrets.compare_digest(expected, payload["fingerprint"]):
        db.session.rollback()
        return jsonify({"error": "Invalid unsubscribe link."}), 400

    db.session.execute(
        users.update()
        .where(users.c.id == student["id"])
        .values(weekly_report_enabled=False)
    )
    db.session.commit()

    return jsonify({
        "message": "Progress report emails have been stopped."
    }), 200

@parent_reports_bp.post(
    "/classes/<int:classroom_id>/students/<int:student_id>/email"
)
@jwt_required()
@limiter.limit("5 per hour")
def correct_student_parent_email(classroom_id: int, student_id: int):
    users = db.metadata.tables["users"]
    classes = db.metadata.tables["classrooms"]
    memberships = db.metadata.tables["class_memberships"]

    teacher = db.session.execute(
        select(users.c.id, users.c.role)
        .where(users.c.id == int(get_jwt_identity()))
    ).mappings().one_or_none()

    if teacher is None:
        return jsonify({"error": "User account no longer exists."}), 404

    if teacher["role"] != "teacher":
        return jsonify({
            "error": "Only teachers can correct parent email."
        }), 403

    body = request.get_json(silent=True)

    if not isinstance(body, dict):
        return jsonify({"error": "Request body must be an object."}), 400

    cleaned = body.copy()
    email_value = cleaned.get("parent_email")

    if isinstance(email_value, str):
        cleaned["parent_email"] = email_value.strip()

    try:
        data = ParentEmailSchema().load(cleaned)
    except ValidationError as error:
        return jsonify({
            "error": "Enter a valid parent email.",
            "details": error.messages,
        }), 400

    if not isinstance(data, dict):
        return jsonify({"error": "Invalid request body."}), 400

    email = data.get("parent_email")

    if not isinstance(email, str) or len(email) > 255:
        return jsonify({"error": "Enter a valid parent email."}), 400

    classroom = db.session.execute(
        select(classes.c.id)
        .where(
            classes.c.id == classroom_id,
            classes.c.teacher_id == teacher["id"],
        )
        .with_for_update()
    ).scalar_one_or_none()

    if classroom is None:
        db.session.rollback()
        return jsonify({"error": "Class not found."}), 404

    membership = db.session.execute(
        select(memberships.c.id)
        .where(
            memberships.c.classroom_id == classroom_id,
            memberships.c.student_id == student_id,
        )
        .with_for_update()
    ).scalar_one_or_none()

    if membership is None:
        db.session.rollback()
        return jsonify({"error": "Current class member not found."}), 404

    student = db.session.execute(
        select(users)
        .where(
            users.c.id == student_id,
            users.c.role == "student",
        )
        .with_for_update()
    ).mappings().one_or_none()

    if student is None:
        db.session.rollback()
        return jsonify({"error": "Student not found."}), 404

    if (
        student["parent_email_verified_at"] is not None
        and student["parent_email"] is not None
        and student["parent_email"].casefold() == email.casefold()
    ):
        db.session.rollback()
        return jsonify({
            "error": "Enter a different email for parent email correction."
        }), 409

    return send_parent_verification(
        student,
        email,
        requested_by_teacher=True,
    )

@parent_reports_bp.post("/resume")
@limiter.limit("20 per hour")
def resume_parent_reports():
    body = request.get_json(silent=True)

    if (
        not isinstance(body, dict)
        or set(body) != {"token", "confirm"}
        or body.get("confirm") is not True
    ):
        return jsonify({
            "error": "A parent link and confirmation are required."
        }), 400

    try:
        payload = read_parent_unsubscribe_token(body["token"])
    except ValueError:
        return jsonify({"error": "Invalid parent report link."}), 400

    users = db.metadata.tables["users"]

    student = db.session.execute(
        select(users)
        .where(users.c.id == payload["student_id"])
        .with_for_update()
    ).mappings().one_or_none()

    if (
        student is None
        or student["role"] != "student"
        or student["parent_email"] is None
        or student["parent_email_verified_at"] is None
    ):
        db.session.rollback()
        return jsonify({"error": "Invalid parent report link."}), 400

    expected = verification_fingerprint(
        student["parent_email"],
        student["parent_email_verified_at"],
    )

    if not secrets.compare_digest(expected, payload["fingerprint"]):
        db.session.rollback()
        return jsonify({"error": "Invalid parent report link."}), 400

    db.session.execute(
        users.update()
        .where(users.c.id == student["id"])
        .values(weekly_report_enabled=True)
    )
    db.session.commit()

    return jsonify({
        "message": "Progress report emails are enabled again."
    }), 200